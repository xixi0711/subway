#!/usr/bin/env python3
"""数据库迁移脚本：
1. 从列车时刻表中删除所属交路编号列
2. 在线路信息表中添加路径相关字段
3. 从线路路径信息表迁移数据到线路信息表
4. 删除线路路径信息表
"""

import sqlite3
import os

DB_PATH = './subway.db'

def migrate_database():
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("[INFO] 开始数据库迁移...")
        
        # 1. 检查线路信息表结构，添加缺失的字段
        print("[INFO] 1. 更新线路信息表结构...")
        
        # 获取现有列名
        cursor.execute("PRAGMA table_info(线路信息表)")
        existing_columns = [col[1] for col in cursor.fetchall()]
        
        columns_to_add = [
            ('起点站点', 'TEXT', ''),
            ('终点站点', 'TEXT', ''),
            ('站点列表', 'TEXT', ''),
            ('线路颜色', 'TEXT', "'#1890ff'")
        ]
        
        for col_name, col_type, default_val in columns_to_add:
            if col_name not in existing_columns:
                print(f"  添加字段: {col_name}")
                if default_val:
                    cursor.execute(f"ALTER TABLE 线路信息表 ADD COLUMN {col_name} {col_type} DEFAULT {default_val}")
                else:
                    cursor.execute(f"ALTER TABLE 线路信息表 ADD COLUMN {col_name} {col_type}")
        
        # 2. 迁移线路路径信息表数据到线路信息表
        print("[INFO] 2. 迁移线路路径信息表数据...")
        
        # 检查线路路径信息表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='线路路径信息表'")
        if cursor.fetchone():
            # 读取线路路径信息
            cursor.execute("SELECT 线路编号, 起点站点, 终点站点, 站点列表, 线路颜色 FROM 线路路径信息表")
            path_data = cursor.fetchall()
            
            for line_id, start_station, end_station, station_list, line_color in path_data:
                cursor.execute("""
                    UPDATE 线路信息表 
                    SET 起点站点 = ?, 终点站点 = ?, 站点列表 = ?, 线路颜色 = ?
                    WHERE 线路编号 = ?
                """, (start_station, end_station, station_list, line_color or '#1890ff', line_id))
                print(f"  迁移线路 {line_id} 的路径信息")
            
            # 删除线路路径信息表
            print("[INFO] 3. 删除线路路径信息表...")
            cursor.execute("DROP TABLE 线路路径信息表")
        
        # 3. 从列车时刻表中删除所属交路编号列
        print("[INFO] 4. 修改列车时刻表...")
        
        # 获取现有列名
        cursor.execute("PRAGMA table_info(列车时刻表)")
        timetable_columns = [col[1] for col in cursor.fetchall()]
        
        if '所属交路编号' in timetable_columns:
            # SQLite不支持直接删除列，需要创建新表并迁移数据
            print("  创建新的列车时刻表临时表...")
            cursor.execute("""
                CREATE TABLE 列车时刻表_new (
                    列车编号 TEXT,
                    所属线路编号 TEXT NOT NULL,
                    运行方向 TEXT NOT NULL,
                    途经站点编号 TEXT NOT NULL,
                    到站时间 TEXT NOT NULL,
                    发车时间 TEXT NOT NULL,
                    PRIMARY KEY (列车编号, 途经站点编号)
                )
            """)
            
            # 迁移数据
            cursor.execute("""
                INSERT INTO 列车时刻表_new (列车编号, 所属线路编号, 运行方向, 途经站点编号, 到站时间, 发车时间)
                SELECT 列车编号, 所属线路编号, 运行方向, 途经站点编号, 到站时间, 发车时间 FROM 列车时刻表
            """)
            
            # 删除旧表
            cursor.execute("DROP TABLE 列车时刻表")
            
            # 重命名新表
            cursor.execute("ALTER TABLE 列车时刻表_new RENAME TO 列车时刻表")
            print("  已删除所属交路编号列")
        
        conn.commit()
        print("[INFO] 数据库迁移完成！")
        
    except Exception as e:
        print(f"[ERROR] 数据库迁移失败: {e}")
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    if os.path.exists(DB_PATH):
        migrate_database()
    else:
        print(f"[ERROR] 数据库文件不存在: {DB_PATH}")