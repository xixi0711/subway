# 客流计算模块
import sqlite3

def get_db_connection():
    """获取数据库连接"""
    return sqlite3.connect('subway.db')

def close_db_connection(conn):
    """关闭数据库连接"""
    if conn:
        conn.close()

def calculate_passenger_flow():
    """计算客流数据"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        cursor.execute('SELECT 站点编号 FROM 站点信息表')
        stations = [row[0] for row in cursor.fetchall()]
        
        import random
        import time
        
        for station in stations:
            date = time.strftime('%Y-%m-%d')
            inflow = random.randint(1000, 10000)
            outflow = random.randint(1000, 10000)
            
            cursor.execute('SELECT COUNT(*) FROM 客流统计表 WHERE 站点编号=? AND 统计日期=?', (station, date))
            if cursor.fetchone()[0] == 0:
                cursor.execute('INSERT INTO 客流统计表 (站点编号, 统计日期, 进站人数, 出站人数, 总客流, 统计时间) VALUES (?, ?, ?, ?, ?, ?)',
                            (station, date, inflow, outflow, inflow + outflow, time.strftime('%Y-%m-%d %H:%M:%S')))
        
        conn.commit()
        return {"status": "success", "message": "客流计算完成"}
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        close_db_connection(conn)

def get_station_passenger_flow(station_id, start_date=None, end_date=None):
    """获取站点客流数据"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        if start_date and end_date:
            cursor.execute('SELECT * FROM 客流统计表 WHERE 站点编号=? AND 统计日期 BETWEEN ? AND ? ORDER BY 统计日期 DESC', 
                          (station_id, start_date, end_date))
        else:
            cursor.execute('SELECT * FROM 客流统计表 WHERE 站点编号=? ORDER BY 统计日期 DESC LIMIT 7', (station_id,))
        rows = cursor.fetchall()
        
        result = []
        for row in rows:
            result.append({
                '统计ID': row[0],
                '站点编号': row[1],
                '统计日期': row[2],
                '进站人数': row[3],
                '出站人数': row[4],
                '总客流': row[5],
                '统计时间': row[6]
            })
        
        return result
    finally:
        close_db_connection(conn)

def get_top_stations(limit=5):
    """获取客流最多的站点"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT 站点编号, SUM(总客流) as 总客流 FROM 客流统计表 GROUP BY 站点编号 ORDER BY 总客流 DESC LIMIT ?', (limit,))
        rows = cursor.fetchall()
        
        result = []
        for row in rows:
            result.append({
                '站点编号': row[0],
                '总客流': row[1]
            })
        
        return result
    finally:
        close_db_connection(conn)