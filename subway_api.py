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
import sqlite3
import json
import re
import requests
import time
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

from contextlib import asynccontextmanager

from cache_utils import (
    get_cached_response,
    cache_response,
    get_cached_db_knowledge,
    cache_db_knowledge,
    get_cache_stats,
    clear_all_caches
)
from rag_knowledge_base import (
    get_retrieval_context,
    add_knowledge,
    build_knowledge_base,
    rag_system
)
from intent_recognition import (
    recognize_intent,
    get_intent_name,
    route_question,
    parse_db_query,
    INTENT_DB_QUERY,
    INTENT_KNOWLEDGE,
    INTENT_CHAT
)

from langchain_agent import get_agent, LangChainAgent

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
ARK_API_URL = os.environ.get("ARK_API_URL", "https://ark.cn-beijing.volces.com/api/v3/chat/completions")
MODEL_NAME = os.environ.get("MODEL_NAME", "ep-20260407211615-tr6lq")

USE_OLLAMA = os.environ.get("USE_OLLAMA", "false").lower() == "true"
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen:7b")

print(f"火山引擎API配置: URL={ARK_API_URL}, Model={MODEL_NAME}")
print(f"Ollama配置: {'启用' if USE_OLLAMA else '禁用'}, 模型: {OLLAMA_MODEL}")

# 构建RAG知识库
print("=" * 50)
print("正在初始化RAG知识库...")
try:
    count = build_knowledge_base("./knowledge_base")
    print(f"RAG知识库构建完成，共加载 {count} 个文档")
except Exception as e:
    print(f"RAG知识库初始化失败: {e}")

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

# 数据库连接函数
def get_db_connection():
    """获取数据库连接"""
    print(f"正在连接数据库: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    print("数据库连接成功")
    return conn

# 关闭数据库连接
def close_db_connection(conn):
    """关闭数据库连接"""
    try:
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"关闭数据库连接失败: {e}")
        try:
            conn.close()
        except:
            pass

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
    """创建或更新线路信息"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # 检查线路是否存在
            cursor.execute("SELECT * FROM 线路信息表 WHERE 线路编号 = ?", (line_data['线路编号'],))
            existing_line = cursor.fetchone()
            
            if existing_line:
                # 更新线路
                cursor.execute("""
                    UPDATE 线路信息表 
                    SET 线路名称 = ?, 首班车时间 = ?, 末班车时间 = ? 
                    WHERE 线路编号 = ?
                """, (line_data['线路名称'], line_data['首班车时间'], line_data['末班车时间'], line_data['线路编号']))
            else:
                # 创建线路
                cursor.execute("""
                    INSERT INTO 线路信息表 (线路编号, 线路名称, 首班车时间, 末班车时间) 
                    VALUES (?, ?, ?, ?)
                """, (line_data['线路编号'], line_data['线路名称'], line_data['首班车时间'], line_data['末班车时间']))
            
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
                    SET 所属线路编号 = ?, 所属交路编号 = ?, 运行方向 = ?, 到站时间 = ?, 发车时间 = ? 
                    WHERE 列车编号 = ? AND 途经站点编号 = ?
                """, (timetable_data['所属线路编号'], timetable_data['所属交路编号'], 
                       timetable_data['运行方向'], timetable_data['到站时间'], 
                       timetable_data['发车时间'], timetable_data['列车编号'], 
                       timetable_data['途经站点编号']))
            else:
                # 创建时刻表
                cursor.execute("""
                    INSERT INTO 列车时刻表 (列车编号, 所属线路编号, 所属交路编号, 运行方向, 途经站点编号, 到站时间, 发车时间) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (timetable_data['列车编号'], timetable_data['所属线路编号'], 
                       timetable_data['所属交路编号'], timetable_data['运行方向'], 
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

@app.post("/api/ai-query")
async def ai_query(request: dict):
    """
    增强版AI智能问答接口

    特性：
    1. 缓存加速：重复问题直接返回缓存结果
    2. 意图识别：根据问题类型走不同处理路径
    3. RAG增强：结合知识库检索提升回答质量
    """
    try:
        question = request.get('question', '').strip()
        user_id = request.get('user_id', 'default')

        if not question:
            return {"code": 200, "message": "success", "data": {
                "answer": "您好！我是地铁智能助手，有什么可以帮您的吗？"
            }}

        start_time = time.time()

        # 禁用缓存，确保实时查询数据库
        # cached_answer = get_cached_response(question)
        # if cached_answer:
        #     return {"code": 200, "message": "success", "data": {
        #         "answer": cached_answer,
        #         "cached": True,
        #         "intent": None,
        #         "response_time": time.time() - start_time
        #     }}

        intent = recognize_intent(question)
        intent_name = get_intent_name(intent)
        
        print(f"[DEBUG] 用户问题: {question}")
        print(f"[DEBUG] 识别意图: {intent_name} (代码: {intent})")

        if intent == INTENT_CHAT:
            chat_response = handle_chat_intent(question)
            print(f"[DEBUG] 闲聊响应: {chat_response}")
            if chat_response:
                cache_response(question, chat_response)
                return {"code": 200, "message": "success", "data": {
                    "answer": chat_response,
                    "intent": intent_name,
                    "response_time": time.time() - start_time
                }}

        # 使用传统方式处理（稳定可靠）
        print("[DEBUG] 使用传统方式处理")

        subway_knowledge = get_subway_knowledge_from_db()
        print(f"[DEBUG] 数据库知识长度: {len(subway_knowledge)} 字符")

        if intent == INTENT_DB_QUERY:
            db_query = parse_db_query(question)
            print(f"[DEBUG] 解析的数据库查询: {db_query}")
            if db_query and 'type' in db_query:
                query_type = db_query['type']
                
                # 客流数据相关查询
                if query_type.startswith('passenger_flow'):
                    if query_type == 'passenger_flow_station' and 'station' in db_query:
                        station = db_query['station']
                        flow_data = get_station_passenger_flow(station)
                        if flow_data:
                            subway_knowledge += f"\n{station}站客流数据：\n"
                            for item in flow_data:
                                subway_knowledge += f"- {item['统计日期']}：进站{item['进站人数']}人，出站{item['出站人数']}人，总客流{item['总客流']}人\n"
                    elif query_type == 'passenger_flow_top':
                        top_stations = get_top_stations(5)
                        if top_stations:
                            subway_knowledge += "\n客流最多的站点：\n"
                            for i, station in enumerate(top_stations, 1):
                                subway_knowledge += f"{i}. {station['站点编号']}站：总客流{station['总客流']}人\n"
                    elif query_type == 'passenger_flow_stats':
                        conn = get_db_connection()
                        try:
                            cursor = conn.cursor()
                            cursor.execute('SELECT SUM(总客流) as 总客流 FROM 客流统计表')
                            total_flow = cursor.fetchone()[0] or 0
                            cursor.execute('SELECT COUNT(DISTINCT 站点编号) as 站点数量 FROM 客流统计表')
                            station_count = cursor.fetchone()[0] or 0
                            cursor.execute('SELECT MIN(统计日期) as 开始日期, MAX(统计日期) as 结束日期 FROM 客流统计表')
                            date_range = cursor.fetchone()
                            start_date = date_range[0] or ''
                            end_date = date_range[1] or ''
                            
                            subway_knowledge += f"\n客流统计概览：\n"
                            subway_knowledge += f"- 总客流：{total_flow}人次\n"
                            subway_knowledge += f"- 统计站点：{station_count}个\n"
                            subway_knowledge += f"- 统计日期：{start_date} 至 {end_date}\n"
                        finally:
                            close_db_connection(conn)

        knowledge_context = ""
        if intent == INTENT_KNOWLEDGE:
            knowledge_context = get_retrieval_context(question, k=3)
            if knowledge_context:
                print(f"RAG检索到 {len(knowledge_context)} 字的相关知识")

        answer = generate_answer_with_context(
            question,
            subway_knowledge,
            knowledge_context
        )

        # 禁用缓存，确保实时查询
        # cache_response(question, answer)

        return {"code": 200, "message": "success", "data": {
            "answer": answer,
            "intent": intent_name,
            "response_time": time.time() - start_time
        }}
    except Exception as e:
        print(f"AI查询错误详情: {e}")
        import traceback
        traceback.print_exc()
        return {"code": 500, "message": "error", "data": {
            "answer": f"抱歉，系统出现错误：{str(e)}"
        }}


def get_subway_knowledge_from_db() -> str:
    """从数据库获取地铁领域知识，不使用缓存，确保实时查询"""
    print("[DB] 正在从数据库查询实时数据...")
    subway_knowledge = ""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()

            cursor.execute('SELECT * FROM 线路信息表')
            lines = cursor.fetchall()

            cursor.execute('SELECT * FROM 站点信息表')
            stations = cursor.fetchall()

            subway_knowledge += "地铁线路信息：\n"
            for line in lines:
                line_id, line_name, first_time, last_time = line
                
                line_stations = []
                for station in stations:
                    station_id, station_line_ids, transfer_lines, station_order, station_name, x, y, desc = station
                    if line_id in station_line_ids.split(','):
                        line_stations.append({
                            'station_id': station_id,
                            'station_name': station_name,
                            'transfer_lines': transfer_lines,
                            'station_order': station_order
                        })
                
                line_stations.sort(key=lambda s: s['station_order'])
                
                subway_knowledge += f"- {line_name}（{line_id}）：共{len(line_stations)}个站点，"
                subway_knowledge += f"首班车时间{first_time}，末班车时间{last_time}\n"
                subway_knowledge += f"  站点列表：{'、'.join([s['station_name'] + '(' + s['station_id'] + ')' for s in line_stations])}\n"
                
                transfer_stations = [s for s in line_stations if s['transfer_lines'] and s['transfer_lines'] != '-']
                if transfer_stations:
                    subway_knowledge += f"  换乘站：{'、'.join([s['station_name'] + '(' + s['station_id'] + ')可换乘' + s['transfer_lines'] for s in transfer_stations])}\n"

        finally:
            close_db_connection(conn)
    except Exception as e:
        print(f"获取数据库知识失败: {e}")
        subway_knowledge = get_default_knowledge()

    print(f"[DB] 数据库查询完成，获取了 {len(stations)} 个站点数据")
    return subway_knowledge


def get_default_knowledge() -> str:
    """获取默认地铁知识"""
    return """地铁线路信息：
- L1线：首班车时间06:00，末班车时间23:00
- L2线：首班车时间06:00，末班车时间23:00
- L3线：首班车时间06:00，末班车时间23:00

站点信息：
- S1站：可换乘L1线
- S2站：可换乘L1线
- S3站：可换乘L1线
- S5站：可换乘L2线
- S6站：可换乘L2线
- S7站：可换乘L2线
- S8站：可换乘L2线
- S9站：可换乘L3线
- S10站：可换乘L3线
"""


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


def generate_answer_with_context(
    question: str,
    subway_knowledge: str,
    knowledge_context: str = ""
) -> str:
    """结合上下文生成回答"""
    system_content = f"""你是一个专业、友好、详细的地铁信息查询助手。

【可用的地铁信息】
{subway_knowledge}

【重要】请完整、认真地阅读【可用的地铁信息】，然后给出详细回答！

【回答要求】
1. 基于上面【可用的地铁信息】回答，不要编造不存在的信息
2. 回答要尽可能详细、清晰、有条理
3. 回答时要包含所有相关信息，包括：
   - 涉及的线路名称和编号
   - 涉及的站点名称和编号
   - 换乘信息
   - 首末班车时间（如果有的话）
   - 其他相关数据
4. 结构清晰，使用列表或分段方式组织内容
5. 即使不确定，也要根据现有信息给出最佳猜测或建议，绝对不要说"抱歉"！
6. 不要提到"根据您提供的信息"或类似表述

【用户的问题】"""

    if knowledge_context:
        system_content += f"\n\n参考知识：\n{knowledge_context}"

    # 使用Ollama本地模型
    if USE_OLLAMA:
        try:
            print(f"[DEBUG] 使用Ollama本地模型生成回答")
            
            from langchain_community.llms import Ollama
            llm = Ollama(model=OLLAMA_MODEL, temperature=0.1)
            
            knowledge_info = subway_knowledge
            if knowledge_context:
                knowledge_info += f"\n\n参考知识：\n{knowledge_context}"
            
            print(f"[DEBUG] 输入知识长度: {len(knowledge_info)} 字符")
            
            user_prompt = f"""你是地铁信息查询专家。仔细阅读下面的地铁数据库信息，然后准确回答问题。

【地铁线路数据库】
{knowledge_info}

【用户问题】
{question}

【回答规则】
- 必须严格基于上面的数据库信息回答
- 数字和名称必须完全准确
- 站点数量要精确统计
- 首末班车时间要说明具体线路
- 路线查询要说明详细的换乘方案
- 用自然、友好的中文表达
- 如果数据库中没有相关信息，说明"暂无相关信息"

开始回答："""
            
            answer = llm(user_prompt)
            print(f"[DEBUG] Ollama模型回答: {answer}")
            
            answer = answer.strip().replace("问题：", "").replace("回答：", "").replace("答：", "").replace("答案：", "").strip()
            
            return answer
        except Exception as e:
            print(f"Ollama模型调用失败: {e}")
            import traceback
            traceback.print_exc()
            pass
    
    # 使用API模型
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ARK_API_KEY}"
    }

    # 优化消息格式：将数据库知识和RAG检索知识放在user消息中
    knowledge_info = f"【可用的地铁信息】\n{subway_knowledge}"
    if knowledge_context:
        knowledge_info += f"\n\n【参考知识】\n{knowledge_context}"
    
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": "你是一个专业、友好、详细的地铁信息查询助手。请根据提供的地铁信息回答用户问题。"},
            {"role": "user", "content": f"{knowledge_info}\n\n【用户的问题】{question}"}
        ],
        "temperature": 0.7,
        "max_tokens": 2000,
        "stream": False
    }

    try:
        response = requests.post(
            ARK_API_URL,
            headers=headers,
            json=payload,
            timeout=30
        )

        response_data = response.json()

        if "choices" in response_data and len(response_data["choices"]) > 0:
            choice = response_data["choices"][0]
            if "message" in choice and "content" in choice["message"]:
                return choice["message"]["content"]

    except Exception as e:
        print(f"AI API调用失败: {e}")

    return "抱歉，系统暂时无法处理您的请求，请稍后再试。"


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
    """获取所有线路的路径信息"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM 线路路径信息表')
            lines = []
            for row in cursor.fetchall():
                line = {
                    "路径ID": row[0],
                    "线路编号": row[1],
                    "起点站点": row[2],
                    "终点站点": row[3],
                    "站点列表": row[4],
                    "线路颜色": row[5],
                    "线路名称": row[1]
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
    """添加或更新线路路径信息"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT OR REPLACE INTO 线路路径信息表 (路径ID, 线路编号, 起点站点, 终点站点, 站点列表, 线路颜色)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (line_data['path_id'], line_data['line_id'], line_data['start_station'], 
                  line_data['end_station'], line_data['station_list'], line_data['line_color']))
            conn.commit()
            return {"code": 200, "message": "success", "data": {"路径ID": line_data['path_id']}}
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
    """删除线路路径信息"""
    try:
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM 线路路径信息表 WHERE 路径ID = ?', (path_id,))
            conn.commit()
            return {"code": 200, "message": "success", "data": {"路径ID": path_id}}
        finally:
            close_db_connection(conn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=5000,
        timeout_keep_alive=120
    )
