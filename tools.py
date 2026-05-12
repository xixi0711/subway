"""
工具模块 - 包含客流统计分析和路径规划工具

工具调用规范：
- 输入：结构化字典
- 输出：结构化字典，包含 'success'、'data'、'message' 字段
"""

from typing import Dict, Any, List, Tuple
import sqlite3
from collections import defaultdict
from queue import Queue
import threading

DB_PATH = './subway.db'

# 数据库连接池
class ConnectionPool:
    def __init__(self, max_connections=5):
        self.max_connections = max_connections
        self.pool = Queue(maxsize=max_connections)
        self.lock = threading.Lock()
        # 预创建连接
        for _ in range(min(2, max_connections)):
            conn = self._create_connection()
            if conn:
                self.pool.put(conn)
    
    def _create_connection(self):
        """创建新的数据库连接"""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            print(f"[DB] 创建数据库连接失败: {e}")
            return None
    
    def get_connection(self):
        """从连接池获取连接"""
        try:
            # 先尝试从池中获取
            if not self.pool.empty():
                return self.pool.get(timeout=1)
            # 如果池为空且未达到最大连接数，创建新连接
            with self.lock:
                if self.pool.qsize() < self.max_connections:
                    conn = self._create_connection()
                    if conn:
                        return conn
            # 等待可用连接
            return self.pool.get(timeout=5)
        except Exception as e:
            print(f"[DB] 获取数据库连接失败: {e}")
            return self._create_connection()
    
    def release_connection(self, conn):
        """释放连接回连接池"""
        try:
            if conn:
                # 只在池未满时放回
                if self.pool.qsize() < self.max_connections:
                    self.pool.put(conn, block=False)
                else:
                    conn.close()
        except Exception as e:
            print(f"[DB] 释放数据库连接失败: {e}")
            try:
                conn.close()
            except:
                pass

# 全局连接池实例
_connection_pool = ConnectionPool(max_connections=5)

def get_db_connection():
    """从连接池获取数据库连接"""
    return _connection_pool.get_connection()


def close_db_connection(conn):
    """释放数据库连接回连接池"""
    _connection_pool.release_connection(conn)


class PassengerFlowAnalyzer:
    """
    客流统计分析工具
    
    功能：
    1. 站点客流查询
    2. 客流排行统计
    3. 客流趋势分析
    """
    
    @staticmethod
    def analyze_station_flow(station_id: str) -> Dict[str, Any]:
        """
        查询指定站点的客流数据
        
        Args:
            station_id: 站点编号（如 S1）
            
        Returns:
            {
                'success': bool,
                'data': {
                    'station_id': 站点编号,
                    'records': [每日客流记录],
                    'summary': {
                        'total_flow': 总客流,
                        'avg_daily_flow': 日均客流,
                        'max_flow': 最大客流,
                        'min_flow': 最小客流
                    }
                },
                'message': str
            }
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 查询该站点的所有客流记录
            cursor.execute('''
                SELECT 统计日期, 进站人数, 出站人数, 总客流 
                FROM 客流统计表 
                WHERE 站点编号 = ? 
                ORDER BY 统计日期 DESC
            ''', (station_id,))
            
            records = []
            total_flow = 0
            flows = []
            
            for row in cursor.fetchall():
                record = {
                    'date': row[0],
                    'in_flow': row[1],
                    'out_flow': row[2],
                    'total_flow': row[3]
                }
                records.append(record)
                total_flow += row[3]
                flows.append(row[3])
            
            summary = {
                'total_flow': total_flow,
                'avg_daily_flow': round(total_flow / len(flows), 2) if flows else 0,
                'max_flow': max(flows) if flows else 0,
                'min_flow': min(flows) if flows else 0
            }
            
            close_db_connection(conn)
            
            return {
                'success': True,
                'data': {
                    'station_id': station_id,
                    'records': records,
                    'summary': summary
                },
                'message': f'成功获取 {station_id} 站的客流数据'
            }
            
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'message': f'查询失败: {str(e)}'
            }
    
    @staticmethod
    def get_top_stations(top_n: int = 5) -> Dict[str, Any]:
        """
        获取客流最多的站点排行
        
        Args:
            top_n: 返回前N个站点
            
        Returns:
            {
                'success': bool,
                'data': [
                    {'rank': 排名, 'station_id': 站点编号, 'total_flow': 总客流},
                    ...
                ],
                'message': str
            }
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 站点编号, SUM(总客流) as total 
                FROM 客流统计表 
                GROUP BY 站点编号 
                ORDER BY total DESC 
                LIMIT ?
            ''', (top_n,))
            
            results = []
            for idx, row in enumerate(cursor.fetchall(), 1):
                results.append({
                    'rank': idx,
                    'station_id': row[0],
                    'total_flow': row[1]
                })
            
            close_db_connection(conn)
            
            return {
                'success': True,
                'data': results,
                'message': f'成功获取前 {top_n} 个客流最多的站点'
            }
            
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'message': f'查询失败: {str(e)}'
            }
    
    @staticmethod
    def get_station_flow_by_date(station_id: str, date: str = None) -> Dict[str, Any]:
        """
        获取站点指定日期的客流数据
        
        Args:
            station_id: 站点编号
            date: 日期（格式: YYYY-MM-DD），不传则返回所有日期
            
        Returns:
            {
                'success': bool,
                'data': {
                    'station_id': 站点编号,
                    'date': 查询日期（如果指定）,
                    'records': [客流记录],
                    'summary': {统计信息}
                },
                'message': str
            }
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            if date:
                cursor.execute('''
                    SELECT 统计日期, 进站人数, 出站人数, 总客流 
                    FROM 客流统计表 
                    WHERE 站点编号 = ? AND 统计日期 = ?
                ''', (station_id, date))
            else:
                cursor.execute('''
                    SELECT 统计日期, 进站人数, 出站人数, 总客流 
                    FROM 客流统计表 
                    WHERE 站点编号 = ? 
                    ORDER BY 统计日期 DESC
                ''', (station_id,))
            
            records = []
            total_flow = 0
            flows = []
            
            for row in cursor.fetchall():
                record = {
                    'date': row[0],
                    'in_flow': row[1],
                    'out_flow': row[2],
                    'total_flow': row[3]
                }
                records.append(record)
                total_flow += row[3]
                flows.append(row[3])
            
            summary = {
                'total_flow': total_flow,
                'avg_daily_flow': round(total_flow / len(flows), 2) if flows else 0,
                'max_flow': max(flows) if flows else 0,
                'min_flow': min(flows) if flows else 0
            }
            
            close_db_connection(conn)
            
            return {
                'success': True,
                'data': {
                    'station_id': station_id,
                    'date': date,
                    'records': records,
                    'summary': summary
                },
                'message': f'成功获取 {station_id} 站的客流数据'
            }
            
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'message': f'查询失败: {str(e)}'
            }
    
    @staticmethod
    def get_flow_ranking() -> Dict[str, Any]:
        """
        获取客流排名（最多、第二多、最少）
        
        Returns:
            {
                'success': bool,
                'data': {
                    'top1': {'station_id': 站点, 'total_flow': 客流},
                    'top2': {'station_id': 站点, 'total_flow': 客流},
                    'top3': {'station_id': 站点, 'total_flow': 客流},
                    'bottom1': {'station_id': 站点, 'total_flow': 客流},
                    'bottom2': {'station_id': 站点, 'total_flow': 客流},
                    'all_stations': [所有站点排名]
                },
                'message': str
            }
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 站点编号, SUM(总客流) as total 
                FROM 客流统计表 
                GROUP BY 站点编号 
                ORDER BY total DESC
            ''')
            
            all_stations = []
            for idx, row in enumerate(cursor.fetchall(), 1):
                all_stations.append({
                    'rank': idx,
                    'station_id': row[0],
                    'total_flow': row[1]
                })
            
            result = {
                'top1': all_stations[0] if len(all_stations) >= 1 else None,
                'top2': all_stations[1] if len(all_stations) >= 2 else None,
                'top3': all_stations[2] if len(all_stations) >= 3 else None,
                'bottom1': all_stations[-1] if len(all_stations) >= 1 else None,
                'bottom2': all_stations[-2] if len(all_stations) >= 2 else None,
                'all_stations': all_stations
            }
            
            close_db_connection(conn)
            
            return {
                'success': True,
                'data': result,
                'message': '成功获取客流排名'
            }
            
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'message': f'查询失败: {str(e)}'
            }
    
    @staticmethod
    def get_flow_stats() -> Dict[str, Any]:
        """
        获取整体客流统计概览
        
        Returns:
            {
                'success': bool,
                'data': {
                    'total_flow': 总客流,
                    'station_count': 统计站点数,
                    'date_range': {
                        'start_date': 开始日期,
                        'end_date': 结束日期
                    }
                },
                'message': str
            }
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT SUM(总客流) as total FROM 客流统计表')
            total_flow = cursor.fetchone()[0] or 0
            
            cursor.execute('SELECT COUNT(DISTINCT 站点编号) as count FROM 客流统计表')
            station_count = cursor.fetchone()[0] or 0
            
            cursor.execute('SELECT MIN(统计日期), MAX(统计日期) FROM 客流统计表')
            dates = cursor.fetchone()
            
            close_db_connection(conn)
            
            return {
                'success': True,
                'data': {
                    'total_flow': total_flow,
                    'station_count': station_count,
                    'date_range': {
                        'start_date': dates[0] or '',
                        'end_date': dates[1] or ''
                    }
                },
                'message': '成功获取客流统计概览'
            }
            
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'message': f'查询失败: {str(e)}'
            }


class RoutePlanner:
    """
    路径规划工具
    
    功能：
    1. 查找两站之间的最短路径
    2. 提供换乘方案
    """
    
    @staticmethod
    def get_station_lines(station_id: str) -> List[str]:
        """获取站点所属的线路列表"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 所属线路编号, 可换乘线路 
                FROM 站点信息表 
                WHERE 站点编号 = ?
            ''', (station_id,))
            
            row = cursor.fetchone()
            close_db_connection(conn)
            
            if not row:
                return []
            
            lines = []
            
            # 处理所属线路编号（可能有多个，用逗号分隔）
            if row[0] and row[0] != '-':
                for line in row[0].split(','):
                    line = line.strip()
                    if line and line != '-':
                        lines.append(line)
            
            # 处理可换乘线路
            if row[1] and row[1] != '-':
                for line in row[1].split(','):
                    line = line.strip()
                    if line and line != '-':
                        lines.append(line)
            
            return list(set(lines))
            
        except Exception as e:
            print(f"[ERROR] 获取站点线路失败: {e}")
            return []
    
    @staticmethod
    def get_line_stations(line_id: str) -> List[str]:
        """获取线路的站点列表"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # 查询所属线路编号包含该线路的站点，或可换乘线路包含该线路的站点
            cursor.execute('''
                SELECT 站点编号, 站点序号 
                FROM 站点信息表 
                WHERE 所属线路编号 LIKE ? OR 可换乘线路 LIKE ? 
                ORDER BY 站点序号
            ''', (f'%{line_id}%', f'%{line_id}%'))
            
            stations = [row[0] for row in cursor.fetchall()]
            close_db_connection(conn)
            
            return stations
            
        except Exception as e:
            print(f"[ERROR] 获取线路站点失败: {e}")
            return []
    
    @staticmethod
    def find_route(start_station: str, end_station: str) -> Dict[str, Any]:
        """
        查找从起点站到终点站的最优路径
        
        Args:
            start_station: 起点站编号
            end_station: 终点站编号
            
        Returns:
            {
                'success': bool,
                'data': {
                    'start_station': 起点站,
                    'end_station': 终点站,
                    'routes': [
                        {
                            'path': [站点列表],
                            'transfers': 换乘次数,
                            'stations_count': 站点数,
                            'lines': [途经线路],
                            'description': 路径描述
                        },
                        ...
                    ]
                },
                'message': str
            }
        """
        try:
            if start_station == end_station:
                return {
                    'success': True,
                    'data': {
                        'start_station': start_station,
                        'end_station': end_station,
                        'routes': [{
                            'path': [start_station],
                            'transfers': 0,
                            'stations_count': 1,
                            'lines': [],
                            'description': f'起点和终点相同：{start_station}站'
                        }]
                    },
                    'message': '起点和终点相同'
                }
            
            # 获取起点和终点的线路信息
            start_lines = RoutePlanner.get_station_lines(start_station)
            end_lines = RoutePlanner.get_station_lines(end_station)
            
            if not start_lines:
                return {
                    'success': False,
                    'data': None,
                    'message': f'未找到起点站 {start_station} 的线路信息'
                }
            
            if not end_lines:
                return {
                    'success': False,
                    'data': None,
                    'message': f'未找到终点站 {end_station} 的线路信息'
                }
            
            routes = []
            
            # 情况1：起点和终点在同一条线路上
            common_lines = set(start_lines) & set(end_lines)
            if common_lines:
                line_id = list(common_lines)[0]
                line_stations = RoutePlanner.get_line_stations(line_id)
                
                if start_station in line_stations and end_station in line_stations:
                    start_idx = line_stations.index(start_station)
                    end_idx = line_stations.index(end_station)
                    
                    if start_idx < end_idx:
                        path = line_stations[start_idx:end_idx+1]
                    else:
                        path = line_stations[end_idx:start_idx+1][::-1]
                    
                    routes.append({
                        'path': path,
                        'transfers': 0,
                        'stations_count': len(path),
                        'lines': [line_id],
                        'description': f'乘坐{line_id}号线，从{start_station}到{end_station}，共{len(path)-1}站'
                    })
            
            # 情况2：需要换乘
            # 查找中间换乘站
            all_stations = {}
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT 站点编号, 所属线路编号, 可换乘线路 FROM 站点信息表')
            
            for row in cursor.fetchall():
                station_id = row[0]
                lines = [row[1]]
                if row[2]:
                    lines.extend([l.strip() for l in row[2].split(',') if l.strip()])
                all_stations[station_id] = list(set(lines))
            
            close_db_connection(conn)
            
            # 查找换乘方案
            for start_line in start_lines:
                for end_line in end_lines:
                    if start_line == end_line:
                        continue
                    
                    # 找换乘站
                    transfer_stations = []
                    for station, lines in all_stations.items():
                        if start_line in lines and end_line in lines:
                            transfer_stations.append(station)
                    
                    for transfer_station in transfer_stations:
                        # 计算路径
                        line1_stations = RoutePlanner.get_line_stations(start_line)
                        line2_stations = RoutePlanner.get_line_stations(end_line)
                        
                        if start_station in line1_stations and transfer_station in line1_stations:
                            idx1_start = line1_stations.index(start_station)
                            idx1_transfer = line1_stations.index(transfer_station)
                            path1 = line1_stations[min(idx1_start, idx1_transfer):max(idx1_start, idx1_transfer)+1]
                            if idx1_start > idx1_transfer:
                                path1 = path1[::-1]
                            
                            if end_station in line2_stations and transfer_station in line2_stations:
                                idx2_transfer = line2_stations.index(transfer_station)
                                idx2_end = line2_stations.index(end_station)
                                path2 = line2_stations[min(idx2_transfer, idx2_end):max(idx2_transfer, idx2_end)+1]
                                if idx2_transfer > idx2_end:
                                    path2 = path2[::-1]
                                
                                full_path = path1[:-1] + path2
                                routes.append({
                                    'path': full_path,
                                    'transfers': 1,
                                    'stations_count': len(full_path),
                                    'lines': [start_line, end_line],
                                    'description': f'从{start_station}乘坐{start_line}号线到{transfer_station}换乘{end_line}号线，再到{end_station}，共{len(full_path)-1}站'
                                })
            
            # 按站点数排序，优先推荐站点少的路线
            routes.sort(key=lambda x: x['stations_count'])
            
            return {
                'success': True,
                'data': {
                    'start_station': start_station,
                    'end_station': end_station,
                    'routes': routes[:3]  # 返回前3个最优路线
                },
                'message': f'成功找到 {len(routes)} 条路线' if routes else '未找到合适的路线'
            }
            
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'message': f'路径规划失败: {str(e)}'
            }


class SQLQueryEngine:
    """
    SQL查询引擎 - 为各意图提供专用的手写SQL查询
    
    确保查询操作仅针对预定义的特定表结构
    """
    
    @staticmethod
    def query_station_info(station_id: str = None) -> Dict[str, Any]:
        """
        查询站点信息
        
        Args:
            station_id: 站点编号（可选，不传则查询所有站点）
            
        Returns:
            查询结果
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            if station_id:
                cursor.execute('''
                    SELECT 站点编号, 站点名称, 所属线路编号, 可换乘线路, 站点序号 
                    FROM 站点信息表 
                    WHERE 站点编号 = ?
                ''', (station_id,))
            else:
                cursor.execute('''
                    SELECT 站点编号, 站点名称, 所属线路编号, 可换乘线路, 站点序号 
                    FROM 站点信息表 
                    ORDER BY 所属线路编号, 站点序号
                ''')
            
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            close_db_connection(conn)
            
            return {
                'success': True,
                'data': results,
                'message': f'查询到 {len(results)} 条站点信息'
            }
            
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'message': f'查询失败: {str(e)}'
            }
    
    @staticmethod
    def query_line_info(line_id: str = None) -> Dict[str, Any]:
        """
        查询线路信息
        
        Args:
            line_id: 线路编号（可选，不传则查询所有线路）
            
        Returns:
            查询结果
        """
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            if line_id:
                cursor.execute('''
                    SELECT 线路编号, 线路名称, 首班车时间, 末班车时间, 
                           起点站点, 终点站点, 站点列表, 线路颜色 
                    FROM 线路信息表 
                    WHERE 线路编号 = ?
                ''', (line_id,))
            else:
                cursor.execute('''
                    SELECT 线路编号, 线路名称, 首班车时间, 末班车时间, 
                           起点站点, 终点站点, 站点列表, 线路颜色 
                    FROM 线路信息表 
                    ORDER BY 线路编号
                ''')
            
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            close_db_connection(conn)
            
            return {
                'success': True,
                'data': results,
                'message': f'查询到 {len(results)} 条线路信息'
            }
            
        except Exception as e:
            return {
                'success': False,
                'data': None,
                'message': f'查询失败: {str(e)}'
            }
