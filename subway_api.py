#!/usr/bin/env python3
"""
地铁智能问答系统后端API
确保与DBeaver操作同一个subway.db文件
实现实时双向数据同步

增强功能：
- RAG知识库检索增强
- 意图识别路由
- 回答缓存加速
"""



import os
import json
import re
import requests
import time
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

from contextlib import asynccontextmanager

from cache_utils import (
    clear_all_caches
)
from rag_knowledge_base import (
    get_retrieval_context,
    add_knowledge,
    build_knowledge_base
)
from intent_recognition import (
    get_intent_name,
    parse_entities,
    route_question,
    INTENT_STATION_INFO,
    INTENT_LINE_INFO,
    INTENT_PASSENGER_FLOW,
    INTENT_ROUTE_RECOMMEND,
    INTENT_KNOWLEDGE,
    INTENT_CHAT
)
from tools import (
    SQLQueryEngine,
    PassengerFlowAnalyzer,
    RoutePlanner,
    get_db_connection,
    close_db_connection
)



from calculate_passenger_flow import (
    calculate_passenger_flow,
    get_station_passenger_flow,
    get_top_stations
)



# 加载.env文件
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'subway.db')
print(f"后端服务连接的数据库路径: {DB_PATH}")

ARK_API_KEY = os.environ.get("ARK_API_KEY", "")
ARK_API_URL = os.environ.get("ARK_API_URL", "https://ark.cn-beijing.volces.com/api/v3")
MODEL_NAME = os.environ.get("MODEL_NAME", "ep-20260407211615-tr6lq")
USE_ARK_API = os.environ.get("USE_ARK_API", "false").lower() == "true"

USE_OLLAMA = os.environ.get("USE_OLLAMA", "false").lower() == "true"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")

print(f"火山引擎API配置: 启用={USE_ARK_API}, URL={ARK_API_URL}, Model={MODEL_NAME}")
print(f"Ollama配置: 启用={USE_OLLAMA}, 模型: {OLLAMA_MODEL}")

# 支持的Ollama模型列表
SUPPORTED_MODELS = {
    "ollama-qwen7b": {"name": "Qwen 2.5 7B", "model": "qwen2.5:7b", "description": "Qwen2.5 7B模型，精度高"},
    "ark": {"name": "火山引擎API", "model": MODEL_NAME, "description": "云端API模型"}
}

# 全局模型实例
_ollama_llm = None
_ark_llm = None

def init_llm_models():
    """初始化大模型实例（在应用启动时调用一次）"""
    global _ollama_llm, _ark_llm
    
    print("=" * 50)
    print("正在初始化大模型...")
    
    # 初始化火山引擎API模型
    if USE_ARK_API:
        try:
            from langchain.chat_models import ChatOpenAI
            _ark_llm = ChatOpenAI(
                base_url=ARK_API_URL,
                api_key=ARK_API_KEY,
                model_name=MODEL_NAME,
                temperature=0.5,
                max_tokens=2000
            )
            print(f"[MODEL] 火山引擎API模型 {MODEL_NAME} 加载成功")
        except Exception as e:
            print(f"[WARNING] 无法加载火山引擎API: {e}")
    
    # 初始化Ollama本地模型
    if USE_OLLAMA:
        try:
            from langchain_community.llms import Ollama
            os.environ["OLLAMA_MODELS"] = "D:\\subway_trae_project\\Software"
            os.environ["OLLAMA_GPU_LAYERS"] = "24"
            _ollama_llm = Ollama(
                model=OLLAMA_MODEL,
                temperature=0.3,
                num_ctx=2048
            )
            print(f"[MODEL] Ollama模型 {OLLAMA_MODEL} 加载成功")
        except Exception as e:
            print(f"[WARNING] 无法加载Ollama模型: {e}")
    
    print("大模型初始化完成")
    print("=" * 50)

# 预初始化大模型
init_llm_models()

# 构建RAG知识库（延迟初始化，第一次使用时才加载）
print("=" * 50)
print("RAG知识库将在第一次使用时加载...")
# 注意：vector_db 已存在，不需要重新构建
# 如果需要重建，可以调用 /api/knowledge/build 接口

# 清空缓存
print("正在清空缓存...")
try:
    clear_all_caches()
    print("缓存已清空")
except Exception as e:
    print(f"清空缓存失败: {e}")
print("=" * 50)

app = FastAPI(
    title="地铁智能问答系统 API",
    description="基于subway.db数据库的地铁信息查询API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_encoding_header(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response

# 数据库连接函数（从 tools.py 导入）

# 线路相关接口

@app.get("/api/lines")
async def get_all_lines():
    """查询所有线路信息"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM 线路信息表")
            lines = [dict(row) for row in cursor.fetchall()]
            return {"code": 200, "message": "success", "data": lines}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/lines")
async def create_or_update_line(line_data: dict):
    """创建或更新线路信息（包含路径信息）"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # 检查线路是否存在
            cursor.execute("SELECT * FROM 线路信息表 WHERE 线路编号 = ?", (line_data['线路编号'],))
            existing_line = cursor.fetchone()
            
            if existing_line:
                # 更新线路（包含路径信息）
                cursor.execute("""
                    UPDATE 线路信息表 
                    SET 线路名称 = ?, 首班车时间 = ?, 末班车时间 = ?, 
                        起点站点 = ?, 终点站点 = ?, 站点列表 = ?, 线路颜色 = ?
                    WHERE 线路编号 = ?
                """, (line_data['线路名称'], line_data['首班车时间'], line_data['末班车时间'],
                      line_data.get('起点站点', ''), line_data.get('终点站点', ''), 
                      line_data.get('站点列表', ''), line_data.get('线路颜色', '#1890ff'),
                      line_data['线路编号']))
            else:
                # 创建线路（包含路径信息）
                cursor.execute("""
                    INSERT INTO 线路信息表 (线路编号, 线路名称, 首班车时间, 末班车时间, 
                                            起点站点, 终点站点, 站点列表, 线路颜色) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (line_data['线路编号'], line_data['线路名称'], line_data['首班车时间'], line_data['末班车时间'],
                      line_data.get('起点站点', ''), line_data.get('终点站点', ''), 
                      line_data.get('站点列表', ''), line_data.get('线路颜色', '#1890ff')))
            
            return {"code": 200, "message": "success", "data": line_data}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/lines/{line_id}")
async def delete_line(line_id: str):
    """删除线路信息"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # 删除线路
            cursor.execute("DELETE FROM 线路信息表 WHERE 线路编号 = ?", (line_id,))
            
            return {"code": 200, "message": "success", "data": {"线路编号": line_id, "status": "deleted"}}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 站点相关接口

@app.get("/api/stations")
async def get_stations_by_line(line_id: str = Query(None, description="线路编号")):
    """按线路筛选站点，不提供line_id则返回所有站点（包含地理字段）"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            if line_id:
                cursor.execute('SELECT * FROM 站点信息表 WHERE 所属线路编号 = ? OR 可换乘线路 LIKE ? ORDER BY 所属线路编号, 站点序号', (line_id, f'%{line_id}%'))
            else:
                cursor.execute('SELECT * FROM 站点信息表 ORDER BY 站点编号')
            
            stations = []
            for row in cursor.fetchall():
                row_dict = dict(row)
                # 确保字段存在
                if '站点名称' not in row_dict:
                    row_dict['站点名称'] = row_dict['站点编号']
                if 'x坐标' not in row_dict:
                    row_dict['x坐标'] = 0
                if 'y坐标' not in row_dict:
                    row_dict['y坐标'] = 0
                if '描述' not in row_dict:
                    row_dict['描述'] = ''
                stations.append(row_dict)
            
            return {"code": 200, "message": "success", "data": stations}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/stations")
async def create_or_update_station(station_data: dict):
    """创建或更新站点信息"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # 检查站点是否存在
            cursor.execute('SELECT * FROM 站点信息表 WHERE 站点编号 = ?', (station_data['站点编号'],))
            existing_station = cursor.fetchone()
            
            if existing_station:
                # 更新站点
                cursor.execute('''
                UPDATE 站点信息表 
                SET 所属线路编号 = ?, 可换乘线路 = ?, 站点序号 = ? 
                WHERE 站点编号 = ?
                ''', (station_data['所属线路编号'], station_data['可换乘线路'], station_data['站点序号'], station_data['站点编号']))
            else:
                # 创建站点
                cursor.execute('''
                INSERT INTO 站点信息表 (站点编号, 所属线路编号, 可换乘线路, 站点序号) 
                VALUES (?, ?, ?, ?)
                ''', (station_data['站点编号'], station_data['所属线路编号'], station_data['可换乘线路'], station_data['站点序号']))
            
            return {"code": 200, "message": "success", "data": station_data}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/stations/{station_id}")
async def delete_station(station_id: str):
    """删除站点信息"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # 删除站点
            cursor.execute('DELETE FROM 站点信息表 WHERE 站点编号 = ?', (station_id,))
            
            return {"code": 200, "message": "success", "data": {"站点编号": station_id, "status": "deleted"}}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 时刻表相关接口

@app.get("/api/timetables")
async def get_timetables(line_id: str = Query(..., description="线路编号")):
    """查询列车时刻表"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM 列车时刻表 WHERE 所属线路编号 = ?", (line_id,))
            timetables = [dict(row) for row in cursor.fetchall()]
            return {"code": 200, "message": "success", "data": timetables}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/timetables")
async def create_or_update_timetable(timetable_data: dict):
    """创建或更新时刻表信息"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # 检查时刻表是否存在
            cursor.execute("SELECT * FROM 列车时刻表 WHERE 列车编号 = ? AND 途经站点编号 = ?", 
                          (timetable_data['列车编号'], timetable_data['途经站点编号']))
            existing_timetable = cursor.fetchone()
            
            if existing_timetable:
                # 更新时刻表
                cursor.execute("""
                    UPDATE 列车时刻表 
                    SET 所属线路编号 = ?, 运行方向 = ?, 到站时间 = ?, 发车时间 = ? 
                    WHERE 列车编号 = ? AND 途经站点编号 = ?
                """, (timetable_data['所属线路编号'], 
                       timetable_data['运行方向'], timetable_data['到站时间'], 
                       timetable_data['发车时间'], timetable_data['列车编号'], 
                       timetable_data['途经站点编号']))
            else:
                # 创建时刻表
                cursor.execute("""
                    INSERT INTO 列车时刻表 (列车编号, 所属线路编号, 运行方向, 途经站点编号, 到站时间, 发车时间) 
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (timetable_data['列车编号'], timetable_data['所属线路编号'], 
                       timetable_data['运行方向'], 
                       timetable_data['途经站点编号'], timetable_data['到站时间'], 
                       timetable_data['发车时间']))
            
            return {"code": 200, "message": "success", "data": timetable_data}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/timetables")
async def delete_timetable(timetable_data: dict):
    """删除时刻表信息"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # 删除时刻表
            cursor.execute("DELETE FROM 列车时刻表 WHERE 列车编号 = ? AND 途经站点编号 = ?", 
                          (timetable_data['列车编号'], timetable_data['途经站点编号']))
            
            return {"code": 200, "message": "success", "data": {"列车编号": timetable_data['列车编号'], "途经站点编号": timetable_data['途经站点编号'], "status": "deleted"}}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 刷卡记录相关接口

@app.get("/api/card-records")
async def get_card_records():
    """查询乘客刷卡数据"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM 乘客刷卡数据表 ORDER BY 进站时间 DESC LIMIT 100")
            records = [dict(row) for row in cursor.fetchall()]
            return {"code": 200, "message": "success", "data": records}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/card-records/by-card")
async def get_card_records_by_card(card_id: str = Query(..., description="卡号")):
    """按卡号筛选刷卡记录"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM 乘客刷卡数据表 WHERE 卡号 = ? ORDER BY 进站时间 DESC", (card_id,))
            records = [dict(row) for row in cursor.fetchall()]
            return {"code": 200, "message": "success", "data": records}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/card-records")
async def create_or_update_card_record(record_data: dict):
    """创建或更新刷卡记录"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # 检查记录是否存在（通过交易编号）
            cursor.execute("SELECT * FROM 乘客刷卡数据表 WHERE 交易编号 = ?", (record_data['交易编号'],))
            existing_record = cursor.fetchone()
            
            if existing_record:
                # 更新记录
                cursor.execute("""
                    UPDATE 乘客刷卡数据表 
                    SET 卡号 = ?, 进站站点 = ?, 进站时间 = ?, 出站站点 = ?, 出站时间 = ?, 交易金额 = ?, 途经线路 = ? 
                    WHERE 交易编号 = ?
                """, (record_data['卡号'], record_data['进站站点'], record_data['进站时间'], 
                       record_data['出站站点'], record_data['出站时间'], record_data['交易金额'], 
                       record_data['途经线路'], record_data['交易编号']))
            else:
                # 创建记录
                cursor.execute("""
                    INSERT INTO 乘客刷卡数据表 (交易编号, 卡号, 进站站点, 进站时间, 出站站点, 出站时间, 交易金额, 途经线路)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (record_data['交易编号'], record_data['卡号'], record_data['进站站点'], 
                       record_data['进站时间'], record_data['出站站点'], record_data['出站时间'], 
                       record_data['交易金额'], record_data['途经线路']))
            
            return {"code": 200, "message": "success", "data": record_data}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/card-records/{record_id}")
async def delete_card_record(record_id: str):
    """删除刷卡记录"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # 删除记录
            cursor.execute("DELETE FROM 乘客刷卡数据表 WHERE 交易编号 = ?", (record_id,))
            
            return {"code": 200, "message": "success", "data": {"交易编号": record_id, "status": "deleted"}}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# AI智能问答接口


def format_station_info_for_llm(data):
    """将站点信息格式化为LLM易读的格式 - 增强版，提供更完整数据"""
    if not data:
        return "暂无站点信息"
    
    result = "【站点信息详细数据】\n"
    for idx, station in enumerate(data, 1):
        station_id = station.get('站点编号', '')
        station_name = station.get('站点名称', '')
        line_ids = station.get('所属线路编号', '')
        transfer_lines = station.get('可换乘线路', '')
        station_seq = station.get('站点序号', '')
        
        result += f"\n第{idx}个站点：\n"
        result += f"  • 站点编号：{station_id}\n"
        result += f"  • 站点名称：{station_name if station_name else '无'}\n"
        result += f"  • 所属线路：{line_ids if line_ids else '无'}\n"
        result += f"  • 可换乘线路：{transfer_lines if transfer_lines and transfer_lines != '-' else '无'}\n"
        if station_seq:
            result += f"  • 站点序号：{station_seq}\n"
    
    result += f"\n总计：共{len(data)}个站点"
    return result


def format_line_info_for_llm(data):
    """将线路信息格式化为LLM易读的格式 - 增强版，提供更完整数据"""
    if not data:
        return "暂无线路信息"
    
    result = "【线路信息详细数据】\n"
    for idx, line in enumerate(data, 1):
        line_id = line.get('线路编号', '')
        line_name = line.get('线路名称', '')
        first_time = line.get('首班车时间', '')
        last_time = line.get('末班车时间', '')
        start_station = line.get('起点站点', '')
        end_station = line.get('终点站点', '')
        station_list = line.get('站点列表', '')
        line_color = line.get('线路颜色', '')
        
        result += f"\n第{idx}条线路：\n"
        result += f"  • 线路编号：{line_id}\n"
        result += f"  • 线路名称：{line_name if line_name else '无'}\n"
        result += f"  • 首班车时间：{first_time if first_time else '无'}\n"
        result += f"  • 末班车时间：{last_time if last_time else '无'}\n"
        result += f"  • 起点站：{start_station if start_station else '无'}\n"
        result += f"  • 终点站：{end_station if end_station else '无'}\n"
        result += f"  • 线路颜色：{line_color if line_color else '无'}\n"
        
        if station_list:
            stations = station_list.split(',')
            result += f"  • 站点列表（共{len(stations)}个站点）：\n"
            for i, s in enumerate(stations, 1):
                result += f"    {i}. {s.strip()}\n"
    
    result += f"\n总计：共{len(data)}条线路"
    return result


def format_flow_for_llm(data):
    """将客流数据格式化为LLM易读的格式 - 增强版"""
    if not data:
        return "暂无客流数据"
    
    result = "【客流数据分析详细数据】\n"
    
    if 'station_id' in data:
        # 站点客流数据
        result += f"站点编号：{data['station_id']}\n"
        result += f"\n统计摘要：\n"
        summary = data.get('summary', {})
        result += f"  • 总客流：{summary.get('total_flow', 0)}人次\n"
        result += f"  • 日均客流：{summary.get('avg_daily_flow', 0)}人次\n"
        result += f"  • 最高客流：{summary.get('max_flow', 0)}人次\n"
        result += f"  • 最低客流：{summary.get('min_flow', 0)}人次\n"
        
        records = data.get('records', [])
        if records:
            result += f"\n详细记录（共{len(records)}条）：\n"
            for rec in records:
                result += f"  • {rec.get('date', '')}：进站{rec.get('in_flow',0)}人，出站{rec.get('out_flow',0)}人，总客流{rec.get('total_flow',0)}人\n"
    elif 'top1' in data:
        # 客流排名数据
        result += "客流排名情况：\n"
        if data.get('top1'):
            result += f"  • 第1名（最多）：{data['top1']['station_id']}站，总客流{data['top1']['total_flow']}人次\n"
        if data.get('top2'):
            result += f"  • 第2名：{data['top2']['station_id']}站，总客流{data['top2']['total_flow']}人次\n"
        if data.get('top3'):
            result += f"  • 第3名：{data['top3']['station_id']}站，总客流{data['top3']['total_flow']}人次\n"
        if data.get('bottom2'):
            result += f"  • 倒数第2名：{data['bottom2']['station_id']}站，总客流{data['bottom2']['total_flow']}人次\n"
        if data.get('bottom1'):
            result += f"  • 倒数第1名（最少）：{data['bottom1']['station_id']}站，总客流{data['bottom1']['total_flow']}人次\n"
        
        all_stations = data.get('all_stations', [])
        if all_stations:
            result += f"\n所有站点完整排名（共{len(all_stations)}个）：\n"
            for s in all_stations:
                result += f"  {s['rank']}. {s['station_id']}站：{s['total_flow']}人次\n"
    else:
        # 整体统计数据
        result += f"  • 总客流：{data.get('total_flow', 0)}人次\n"
        result += f"  • 统计站点：{data.get('station_count', 0)}个\n"
        date_range = data.get('date_range', {})
        result += f"  • 统计日期：{date_range.get('start_date', '')} 至 {date_range.get('end_date', '')}\n"
    
    return result


def format_route_info(data):
    """格式化路线信息 - 保留详细信息"""
    if not data or not data.get('routes'):
        return "未找到合适的路线"
    
    start = data['start_station']
    end = data['end_station']
    routes = data['routes']
    
    result = f"路线规划：从{start}站到{end}站\n"
    result += f"共找到 {len(routes)} 条推荐路线\n\n"
    
    for idx, route in enumerate(routes, 1):
        result += f"方案{idx}：{route['description']}\n"
        result += f"  途经站点：{' → '.join(route['path'])}\n"
        result += f"  站点总数：{route['stations_count']}站（含起点终点）\n"
        result += f"  换乘次数：{route['transfers']}次\n"
        result += f"  途经线路：{', '.join(route['lines'])}\n"
        
        if len(route['path']) > 2:
            result += f"  详细路径：\n"
            for i, station in enumerate(route['path']):
                if i == 0:
                    result += f"    {i+1}. {station}（起点）\n"
                elif i == len(route['path']) - 1:
                    result += f"    {i+1}. {station}（终点）\n"
                else:
                    result += f"    {i+1}. {station}\n"
        
        if idx < len(routes):
            result += "\n"
    
    return result





def handle_chat_intent(question: str) -> Optional[str]:
    """处理闲聊类问题"""
    question_lower = question.lower()

    greetings = ["你好", "您好", "嗨", "hi", "hello"]
    for g in greetings:
        if g in question_lower:
            return "您好！我是地铁智能助手，可以帮您查询线路信息、站点信息、时刻表等，有什么可以帮您的吗？"

    thanks = ["谢谢", "感谢", "多谢"]
    for t in thanks:
        if t in question_lower:
            return "不客气！请问还有其他问题吗？"

    goodbye = ["再见", "拜拜", "下次见"]
    for g in goodbye:
        if g in question_lower:
            return "再见！祝您出行愉快！"

    who_patterns = ["你是谁", "叫什么", "名字"]
    for p in who_patterns:
        if p in question_lower:
            return "我是地铁智能问答系统的AI助手，基于火山引擎豆包大模型构建，可以回答您关于地铁线路、站点、时刻表等问题，也可以解答地铁故障处置等规章问题。"

    return None


def build_prompt(question: str, data_str: str, knowledge_context: str = "", history: list = None) -> str:
    """统一的提示词生成函数 - 支持一轮上下文"""
    context_str = ""
    if history and len(history) > 0:
        # 只保留最近一轮对话
        recent_history = history[-1:]
        context_lines = []
        for i, item in enumerate(recent_history):
            if 'user' in item and 'assistant' in item:
                context_lines.append(f"历史问题：{item['user']}")
                context_lines.append(f"历史回答：{item['assistant']}")
        if context_lines:
            context_str = "\n".join(context_lines) + "\n\n"
    
    if knowledge_context:
        return f"""根据下面的参考知识和历史对话回答用户问题。

历史对话：
{context_str}

参考知识：
{knowledge_context}

当前问题：{question}

回答："""
    else:
        return f"""根据下面的数据和历史对话回答用户问题。

历史对话：
{context_str}

数据：
{data_str}

当前问题：{question}

回答："""


@app.get("/api/cache/stats")
async def get_cache_statistics():
    """获取缓存统计信息"""
    return {"code": 200, "message": "success", "data": get_cache_stats()}


@app.post("/api/cache/clear")
async def clear_cache():
    """清除所有缓存（回答缓存和数据库知识缓存）"""
    try:
        from cache_utils import clear_all_caches
        result = clear_all_caches()
        print(f"[CACHE] 缓存已清除: {result}")
        return {"code": 200, "message": "success", "data": result}
    except Exception as e:
        print(f"清除缓存失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/knowledge/add")
async def add_knowledge_item(request: dict):
    """添加知识库条目"""
    content = request.get('content', '').strip()
    metadata = request.get('metadata', {})

    if not content:
        return {"code": 400, "message": "内容不能为空", "data": None}

    success = add_knowledge(content, metadata)
    return {
        "code": 200 if success else 500,
        "message": "success" if success else "failed",
        "data": {"added": success}
    }


@app.post("/api/knowledge/build")
async def build_knowledge_base_from_dir(request: dict = None):
    """从目录构建知识库"""
    directory = request.get('directory', './knowledge_base') if request else './knowledge_base'

    count = build_knowledge_base(directory)
    
    from rag_knowledge_base import reload_vector_db
    reload_vector_db()
    
    return {
        "code": 200,
        "message": "success",
        "data": {"documents_loaded": count}
    }


@app.get("/api/knowledge/retrieve")
async def retrieve_knowledge_items(query: str = Query(..., description="检索查询"), k: int = Query(3, description="返回数量")):
    """检索知识库相关内容"""
    results = get_retrieval_context(query, k=k)
    return {
        "code": 200,
        "message": "success",
        "data": {"context": results}
    }

# 线网数据接口

@app.get("/api/network/stations")
async def get_network_stations():
    """获取所有站点的地理信息（从站点信息表读取）"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM 站点信息表')
            stations = []
            for row in cursor.fetchall():
                station = {
                    "站点编号": row[0],
                    "站点名称": row[4] if len(row) > 4 and row[4] else row[0],
                    "x坐标": row[5] if len(row) > 5 else 0,
                    "y坐标": row[6] if len(row) > 6 else 0,
                    "描述": row[7] if len(row) > 7 else ''
                }
                stations.append(station)
            return {"code": 200, "message": "success", "data": stations}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/network/lines")
async def get_network_lines():
    """获取所有线路的路径信息（从线路信息表读取）"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM 线路信息表')
            lines = []
            for row in cursor.fetchall():
                line = {
                    "路径ID": row[0],
                    "线路编号": row[0],
                    "起点站点": row[4] if len(row) > 4 else '',
                    "终点站点": row[5] if len(row) > 5 else '',
                    "站点列表": row[6] if len(row) > 6 else '',
                    "线路颜色": row[7] if len(row) > 7 else '#1890ff',
                    "线路名称": row[1],
                    "首班车时间": row[2] if len(row) > 2 else '',
                    "末班车时间": row[3] if len(row) > 3 else ''
                }
                lines.append(line)
            return {"code": 200, "message": "success", "data": lines}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/network/stations")
async def add_network_station(station_data: dict):
    """添加或更新站点地理信息（保存到站点信息表）"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # 检查站点是否在站点信息表中
            cursor.execute('SELECT * FROM 站点信息表 WHERE 站点编号 = ?', (station_data['station_id'],))
            existing = cursor.fetchone()
            
            if existing:
                # 更新地理信息
                cursor.execute('''
                UPDATE 站点信息表 SET 站点名称 = ?, x坐标 = ?, y坐标 = ?, 描述 = ?
                WHERE 站点编号 = ?
                ''', (station_data['station_name'], station_data['x'], 
                      station_data['y'], station_data['description'], station_data['station_id']))
            else:
                # 新增站点
                cursor.execute('''
                INSERT INTO 站点信息表 (站点编号, 站点名称, x坐标, y坐标, 描述, 所属线路编号, 可换乘线路, 站点序号)
                VALUES (?, ?, ?, ?, ?, '', '', 0)
                ''', (station_data['station_id'], station_data['station_name'], 
                      station_data['x'], station_data['y'], station_data['description']))
            
            conn.commit()
            return {"code": 200, "message": "success", "data": {"站点编号": station_data['station_id']}}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/network/lines")
async def add_network_line(line_data: dict):
    """添加或更新线路路径信息（保存到线路信息表）"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # 检查线路是否存在
            cursor.execute('SELECT * FROM 线路信息表 WHERE 线路编号 = ?', (line_data['line_id'],))
            existing_line = cursor.fetchone()
            
            if existing_line:
                # 更新线路路径信息
                cursor.execute('''
                UPDATE 线路信息表 
                SET 起点站点 = ?, 终点站点 = ?, 站点列表 = ?, 线路颜色 = ?
                WHERE 线路编号 = ?
                ''', (line_data['start_station'], line_data['end_station'], 
                      line_data['station_list'], line_data['line_color'], 
                      line_data['line_id']))
            else:
                # 创建新线路
                cursor.execute('''
                INSERT INTO 线路信息表 (线路编号, 线路名称, 首班车时间, 末班车时间, 
                                        起点站点, 终点站点, 站点列表, 线路颜色)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (line_data['line_id'], line_data.get('line_name', line_data['line_id']),
                      '', '', line_data['start_station'], line_data['end_station'], 
                      line_data['station_list'], line_data['line_color']))
            
            conn.commit()
            return {"code": 200, "message": "success", "data": {"路径ID": line_data['line_id']}}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/network/stations/{station_id}")
async def delete_network_station(station_id: str):
    """删除站点地理信息（从站点信息表删除）"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM 站点信息表 WHERE 站点编号 = ?', (station_id,))
            conn.commit()
            return {"code": 200, "message": "success", "data": {"站点编号": station_id}}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/network/lines/{path_id}")
async def delete_network_line(path_id: str):
    """删除线路路径信息（从线路信息表删除）"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM 线路信息表 WHERE 线路编号 = ?', (path_id,))
            conn.commit()
            return {"code": 200, "message": "success", "data": {"路径ID": path_id}}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 模型管理接口

@app.get("/api/models")
async def get_supported_models():
    """获取支持的模型列表"""
    models = []
    for key, info in SUPPORTED_MODELS.items():
        models.append({
            "key": key,
            "name": info["name"],
            "description": info["description"]
        })
    return {"code": 200, "message": "success", "data": models}

# 客流数据接口

@app.get("/api/passenger-flow/station/{station_id}")
async def get_station_flow(station_id: str, start_date: str = None, end_date: str = None):
    """获取指定站点的客流数据"""
    try:
        data = get_station_passenger_flow(station_id, start_date, end_date)
        return {"code": 200, "message": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/passenger-flow/top")
async def get_top_passenger_flow(limit: int = Query(10, description="返回数量")):
    """获取客流最多的站点"""
    try:
        data = get_top_stations(limit)
        # 按站点编号排序（S1, S2, ..., S10）
        data.sort(key=lambda x: (len(x['站点编号']), x['站点编号']))
        return {"code": 200, "message": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/passenger-flow/calculate")
async def calculate_flow():
    """重新计算客流数据"""
    try:
        calculate_passenger_flow()
        return {"code": 200, "message": "success", "data": {"status": "客流数据计算完成"}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/passenger-flow/stats")
async def get_passenger_flow_stats():
    """获取客流统计概览"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # 总客流
            cursor.execute('SELECT SUM(总客流) as total_flow FROM 客流统计表')
            total_flow = cursor.fetchone()[0] or 0
            
            # 站点数量
            cursor.execute('SELECT COUNT(DISTINCT 站点编号) as station_count FROM 客流统计表')
            station_count = cursor.fetchone()[0] or 0
            
            # 统计日期范围
            cursor.execute('SELECT MIN(统计日期) as start_date, MAX(统计日期) as end_date FROM 客流统计表')
            date_range = cursor.fetchone()
            start_date = date_range[0] or ''
            end_date = date_range[1] or ''
            
            stats = {
                "totalFlow": total_flow,
                "stationCount": station_count,
                "dateRange": f"{start_date} 至 {end_date}"
            }
            
            return {"code": 200, "message": "success", "data": stats}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




def format_flow_for_llm(data: dict) -> str:
    """
    将客流数据格式化为适合大模型理解的文本格式
    
    Args:
        data: 客流数据分析结果
        
    Returns:
        格式化后的文本
    """
    result = ""
    
    if 'station_id' in data:
        # 站点客流数据
        result += f"站点: {data['station_id']}\n"
        
        if 'date' in data and data['date']:
            result += f"查询日期: {data['date']}\n"
        
        if 'records' in data:
            all_records = data['records']
            result += f"客流记录共 {len(all_records)} 条:\n"
            for record in all_records:
                result += f"  - {record['date']}: 进站{record['in_flow']}人, 出站{record['out_flow']}人, 总客流{record['total_flow']}人\n"
        
        if 'summary' in data:
            summary = data['summary']
            result += "\n统计摘要:\n"
            result += f"  总客流: {summary.get('total_flow', 0)}人次\n"
            result += f"  日均客流: {summary.get('avg_daily_flow', 0)}人次\n"
            result += f"  最大客流: {summary.get('max_flow', 0)}人次\n"
            result += f"  最小客流: {summary.get('min_flow', 0)}人次\n"
    
    elif 'top1' in data:
        # 客流排名数据
        result += "客流排名统计:\n"
        if data['top1']:
            result += f"  第1名: {data['top1']['station_id']}站, 总客流{data['top1']['total_flow']}人次\n"
        if data['top2']:
            result += f"  第2名: {data['top2']['station_id']}站, 总客流{data['top2']['total_flow']}人次\n"
        if data['top3']:
            result += f"  第3名: {data['top3']['station_id']}站, 总客流{data['top3']['total_flow']}人次\n"
        if data['bottom1']:
            result += f"  最少客流: {data['bottom1']['station_id']}站, 总客流{data['bottom1']['total_flow']}人次\n"
        if data['bottom2']:
            result += f"  倒数第2: {data['bottom2']['station_id']}站, 总客流{data['bottom2']['total_flow']}人次\n"
        
        if 'all_stations' in data:
            result += "\n所有站点排名详情:\n"
            for station in data['all_stations']:
                result += f"  第{station['rank']}名: {station['station_id']}站, {station['total_flow']}人次\n"
    
    elif 'total_flow' in data:
        # 整体统计数据
        result += "整体客流统计概览:\n"
        result += f"  总客流: {data['total_flow']}人次\n"
        result += f"  统计站点数: {data.get('station_count', 0)}个\n"
        if 'date_range' in data:
            result += f"  统计周期: {data['date_range'].get('start_date', '')} 至 {data['date_range'].get('end_date', '')}\n"
    
    return result.strip()


async def stream_ollama_response(question: str, data_str: str, knowledge_context: str, llm, is_ollama: bool):
    """
    流式生成Ollama响应（G方案+ H方案整合）
    """
    # 使用 generate_answer_with_context 的提示词逻辑
    if is_ollama:
        if knowledge_context:
            user_prompt = f"""你是地铁信息查询专家。请严格按照下面的参考知识回答用户问题。

参考知识：
{knowledge_context}

问题：{question}

回答要求：
1. 只能使用参考知识中的信息，绝对不能编造任何信息
2. 不要添加任何参考知识中没有的内容或推测
3. 不要说"根据规定"、"一般来说"等不确定的表述
4. 如果参考知识中有明确数字（如重量、尺寸），必须准确使用这些数字
5. 回答要直接、简洁，只输出答案本身
6. 如果参考知识中没有相关信息，只输出"暂无相关信息"

回答："""
        else:
            user_prompt = f"""你是地铁信息查询专家。根据提供的数据回答问题。

数据：
{data_str}

问题：{question}

回答要求：
1. 只输出答案本身，不要添加任何额外说明、免责声明或客套话
2. 不要说明数据来源，不要问用户是否需要更多信息
3. 回答要简洁、直接、准确
4. 如果没有相关信息，只输出"暂无相关信息"

答案："""
    else:
        if knowledge_context:
            user_prompt = f"""你是地铁信息查询专家。请根据下面的参考知识，详细回答用户的问题。

参考知识：
{knowledge_context}

问题：{question}

回答要求：
1. 必须完全基于参考知识回答，不要编造信息
2. 使用参考知识中的具体数据和规定，引用所有相关细节
3. 如果参考知识中有明确数字（如重量、尺寸、时间），必须使用这些数字
4. 回答要详细、自然、有逻辑性，像与人对话一样
5. 可以适当分段，使用列表或步骤说明让回答更清晰
6. 如果参考知识中没有相关信息，只说"暂无相关信息"

回答："""
        else:
            user_prompt = f"""你是地铁信息查询专家。根据提供的数据，详细回答用户的问题。

数据：
{data_str}

问题：{question}

回答要求：
1. 基于提供的数据进行详细解答，包含所有相关信息
2. 使用数据中的具体数字和细节，不要遗漏重要信息
3. 回答要详细、自然、易懂，可以适当组织成段落或列表
4. 对于路线规划，描述清楚每一步怎么走
5. 对于客流数据，说明具体的统计结果和趋势
6. 如果没有相关信息，只输出"暂无相关信息"

答案："""

    try:
        # 使用Ollama的流式接口
        if is_ollama:
            # 直接调用ollama API进行流式输出
            ollama_url = "http://localhost:11434/api/generate"
            payload = {
                "model": llm.model,
                "prompt": user_prompt,
                "stream": True,
                "options": {
                    "temperature": 0.1
                }
            }
            
            response = requests.post(ollama_url, json=payload, stream=True)
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line.decode('utf-8'))
                    if 'response' in chunk:
                        yield f"data: {json.dumps({'content': chunk['response']}, ensure_ascii=False)}\n\n"
                    if chunk.get('done'):
                        break
        else:
            # 火山引擎API也支持流式输出
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {ARK_API_KEY}"
            }
            
            payload = {
                "model": MODEL_NAME,
                "messages": [{"role": "user", "content": user_prompt}],
                "temperature": 0.7,
                "stream": True
            }
            
            response = requests.post(ARK_API_URL, headers=headers, json=payload, stream=True)
            for line in response.iter_lines():
                if line and line.startswith(b'data: '):
                    line = line[6:]
                    if line.strip() == b'[DONE]':
                        break
                    try:
                        chunk = json.loads(line.decode('utf-8'))
                        if 'choices' in chunk and len(chunk['choices']) > 0:
                            delta = chunk['choices'][0].get('delta', {})
                            if 'content' in delta:
                                yield f"data: {json.dumps({'content': delta['content']}, ensure_ascii=False)}\n\n"
                    except:
                        pass
                    
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
    except Exception as e:
        print(f"[ERROR] 流式响应错误: {e}")
        yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"


async def generate_stream_response(request_data: dict):
    """
    生成流式响应数据的辅助函数 - 支持两轮上下文
    """
    try:
        question = request_data.get('question', '').strip()
        user_id = request_data.get('user_id', 'default')
        model_type = request_data.get('model_type', None)
        history = request_data.get('history', [])  # 历史对话上下文

        if not question:
            yield f"data: {json.dumps({'content': '您好！我是地铁智能助手，有什么可以帮您的吗？'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return

        # 判断使用哪个模型
        local_use_ollama = False
        local_use_ark = False
        if model_type == "ollama":
            local_use_ollama = True
            local_use_ark = False
        elif model_type == "ark":
            local_use_ollama = False
            local_use_ark = True
        else:
            DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "ollama")
            if DEFAULT_MODEL == "ark":
                local_use_ollama = False
                local_use_ark = True
            else:
                local_use_ollama = os.environ.get("USE_OLLAMA", "false").lower() == "true"
                local_use_ark = os.environ.get("USE_ARK_API", "false").lower() == "true"

        # 使用预加载的模型
        llm = None
        is_ollama = False
        if local_use_ollama and _ollama_llm:
            llm = _ollama_llm
            is_ollama = True
        elif local_use_ark and _ark_llm:
            llm = _ark_llm

        if not llm:
            yield f"data: {json.dumps({'content': '模型未初始化，请检查配置'}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return

        # 使用小型分类模型进行意图识别（速度更快）
        intent, intent_name, entities = route_question(question)

        # 返回意图信息
        yield f"data: {json.dumps({'intent': intent_name, 'slots': entities}, ensure_ascii=False)}\n\n"

        # 根据意图处理
        if intent == INTENT_CHAT:
            chat_response = handle_chat_intent(question)
            if chat_response:
                yield f"data: {json.dumps({'content': chat_response}, ensure_ascii=False)}\n\n"
                yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
                return

        # 获取相关数据和知识
        knowledge_context = ""
        data_str = ""
        fallback_response = None

        if intent == INTENT_KNOWLEDGE:
            knowledge_context = get_retrieval_context(question, k=3)
            if knowledge_context:
                print(f"RAG检索到 {len(knowledge_context)} 字的相关知识")
        elif intent == INTENT_STATION_INFO:
            station_id = entities.get('stations')[0] if entities.get('stations') else None
            query_result = SQLQueryEngine.query_station_info(station_id)
            if query_result['success']:
                data_str = format_station_info_for_llm(query_result['data'])
            else:
                fallback_response = query_result['message']
        elif intent == INTENT_LINE_INFO:
            line_id = entities.get('lines')[0] if entities.get('lines') else None
            query_result = SQLQueryEngine.query_line_info(line_id)
            if query_result['success']:
                data_str = format_line_info_for_llm(query_result['data'])
            else:
                fallback_response = query_result['message']
        elif intent == INTENT_PASSENGER_FLOW:
            question_lower = question.lower()
            station_id = entities.get('stations')[0] if entities.get('stations') else None

            if any(keyword in question_lower for keyword in ["最多", "第二", "排行", "排名", "最少"]):
                analysis_result = PassengerFlowAnalyzer.get_flow_ranking()
            elif station_id and any(keyword in question_lower for keyword in ["哪一天", "日期", "几号"]):
                import re
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', question)
                date = date_match.group(1) if date_match else None
                analysis_result = PassengerFlowAnalyzer.get_station_flow_by_date(station_id, date)
            elif station_id:
                analysis_result = PassengerFlowAnalyzer.get_station_flow_by_date(station_id)
            else:
                analysis_result = PassengerFlowAnalyzer.get_flow_stats()

            if analysis_result['success']:
                data_str = format_flow_for_llm(analysis_result['data'])
            else:
                fallback_response = analysis_result['message']
        elif intent == INTENT_ROUTE_RECOMMEND:
            start_station = entities.get('start_station')
            end_station = entities.get('end_station')

            if not start_station or not end_station:
                fallback_response = "请告诉我起点站和终点站，我来为您规划路线"
            else:
                route_result = RoutePlanner.find_route(start_station, end_station)
                if route_result['success']:
                    data_str = format_route_info(route_result['data'])
                else:
                    fallback_response = route_result['message']
        else:
            data_str = ""

        if fallback_response:
            yield f"data: {json.dumps({'content': fallback_response}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
            return

        # 开始流式输出回答
        if is_ollama:
            # 使用Ollama的流式接口
            ollama_url = "http://localhost:11434/api/generate"
            user_prompt = build_prompt(question, data_str, knowledge_context, history)
            
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": user_prompt,
                "stream": True,
                "options": {
                    "temperature": 0.3,
                    "num_ctx": 2048,
                    "max_tokens": 1000,
                    "num_gpu": 24
                }
            }
            
            try:
                response = requests.post(ollama_url, json=payload, stream=True)
                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line.decode('utf-8'))
                        if 'response' in chunk:
                            yield f"data: {json.dumps({'content': chunk['response']}, ensure_ascii=False)}\n\n"
                        if chunk.get('done'):
                            break
            except Exception as e:
                print(f"[ERROR] Ollama流式错误: {e}")
                # 备用：使用预加载模型生成完整回答
                try:
                    prompt = build_prompt(question, data_str, knowledge_context, history)
                    answer = llm(prompt)
                    yield f"data: {json.dumps({'content': answer}, ensure_ascii=False)}\n\n"
                except:
                    yield f"data: {json.dumps({'content': '生成回答时出错'}, ensure_ascii=False)}\n\n"
        else:
            # 火山引擎：一次性生成回答
            try:
                prompt = build_prompt(question, data_str, knowledge_context, history)
                answer = llm.predict(prompt)
                yield f"data: {json.dumps({'content': answer}, ensure_ascii=False)}\n\n"
            except Exception as e:
                print(f"[ERROR] 火山引擎API错误: {e}")
                yield f"data: {json.dumps({'content': '生成回答时出错'}, ensure_ascii=False)}\n\n"
            
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    except Exception as e:
        print(f"[ERROR] 流式AI查询错误: {e}")
        import traceback
        traceback.print_exc()
        yield f"data: {json.dumps({'content': f'抱歉，系统出现错误：{str(e)}'}, ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"


@app.post("/api/ai-query/stream")
async def ai_query_stream(request: dict):
    """
    流式输出AI智能问答接口（G方案 + H方案整合）
    支持SSE流式响应，提升用户体验
    """
    return StreamingResponse(
        generate_stream_response(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=5000,
        timeout_keep_alive=120
    )
