# 缓存工具模块
import os
import json
import time

# 缓存目录
CACHE_DIR = "./cache"

def init_cache():
    """初始化缓存目录"""
    os.makedirs(CACHE_DIR, exist_ok=True)

def get_cached_response(question):
    """获取缓存的回答"""
    cache_file = os.path.join(CACHE_DIR, f"{hash(question)}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 检查是否过期（24小时）
                if time.time() - data['timestamp'] < 86400:
                    return data['answer']
        except:
            pass
    return None

def cache_response(question, answer):
    """缓存回答"""
    cache_file = os.path.join(CACHE_DIR, f"{hash(question)}.json")
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({
                'question': question,
                'answer': answer,
                'timestamp': time.time()
            }, f)
    except:
        pass

def get_cached_db_knowledge():
    """获取缓存的数据库知识"""
    cache_file = os.path.join(CACHE_DIR, "db_knowledge.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if time.time() - data['timestamp'] < 3600:
                    return data['knowledge']
        except:
            pass
    return None

def cache_db_knowledge(knowledge):
    """缓存数据库知识"""
    cache_file = os.path.join(CACHE_DIR, "db_knowledge.json")
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({
                'knowledge': knowledge,
                'timestamp': time.time()
            }, f)
    except:
        pass

def get_cache_stats():
    """获取缓存统计"""
    if not os.path.exists(CACHE_DIR):
        return {"cache_count": 0, "cache_size": 0}
    
    cache_count = 0
    cache_size = 0
    for filename in os.listdir(CACHE_DIR):
        filepath = os.path.join(CACHE_DIR, filename)
        if os.path.isfile(filepath):
            cache_count += 1
            cache_size += os.path.getsize(filepath)
    
    return {
        "cache_count": cache_count,
        "cache_size": cache_size
    }

def clear_all_caches():
    """清除所有缓存"""
    if os.path.exists(CACHE_DIR):
        for filename in os.listdir(CACHE_DIR):
            filepath = os.path.join(CACHE_DIR, filename)
            if os.path.isfile(filepath):
                os.remove(filepath)
    return {"status": "success", "message": "缓存已清除"}

init_cache()