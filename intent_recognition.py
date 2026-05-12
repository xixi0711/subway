"""
意图识别模块 - 使用训练好的小型分类模型
"""

from typing import Tuple, Dict, Any
import re
import os

# 意图定义
INTENT_STATION_INFO = 1
INTENT_LINE_INFO = 2
INTENT_PASSENGER_FLOW = 3
INTENT_ROUTE_RECOMMEND = 4
INTENT_KNOWLEDGE = 5
INTENT_CHAT = 6

INTENT_NAMES = {
    INTENT_STATION_INFO: "站点信息查询",
    INTENT_LINE_INFO: "线路信息查询",
    INTENT_PASSENGER_FLOW: "客流数据分析",
    INTENT_ROUTE_RECOMMEND: "线路推荐",
    INTENT_KNOWLEDGE: "知识查询",
    INTENT_CHAT: "闲聊"
}

INTENT_LABELS = ['站点信息查询', '线路信息查询', '客流数据分析', '线路推荐', '知识查询', '闲聊']

# 全局模型实例
_tokenizer = None
_model = None

def load_intent_model(model_path: str = "./intent_model"):
    """加载训练好的意图识别模型"""
    global _tokenizer, _model
    
    if _tokenizer is not None and _model is not None:
        return
    
    try:
        os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        
        _tokenizer = AutoTokenizer.from_pretrained(model_path)
        _model = AutoModelForSequenceClassification.from_pretrained(model_path)
        _model.eval()
        print("[INFO] 意图识别模型加载成功")
    except Exception as e:
        print(f"[ERROR] 加载意图识别模型失败: {e}")

def recognize_intent_with_small_model(question: str) -> int:
    """使用小型分类模型进行意图识别"""
    if not question or not question.strip():
        return INTENT_CHAT
    
    if _tokenizer is None or _model is None:
        load_intent_model()
    
    try:
        inputs = _tokenizer(question, return_tensors='pt', padding=True, truncation=True, max_length=64)
        outputs = _model(**inputs)
        pred = outputs.logits.argmax().item()
        return pred + 1
    except Exception as e:
        print(f"[ERROR] 小型模型意图识别失败: {e}")
        return INTENT_KNOWLEDGE

def get_intent_name(intent: int) -> str:
    """获取意图名称"""
    return INTENT_NAMES.get(intent, "未知")

def parse_entities(question: str) -> Dict[str, Any]:
    """
    从问题中抽取实体信息
    """
    result = {
        'stations': [],
        'lines': [],
        'start_station': None,
        'end_station': None
    }
    
    question_lower = question.lower()
    
    station_matches = re.findall(r's(\d{1,2})', question_lower)
    for match in station_matches:
        station = f"S{int(match)}"
        if station not in result['stations']:
            result['stations'].append(station)
    
    line_matches = re.findall(r'l(\d{1,2})', question_lower)
    for match in line_matches:
        line = f"L{int(match)}"
        if line not in result['lines']:
            result['lines'].append(line)
    
    if len(result['stations']) >= 2:
        result['start_station'] = result['stations'][0]
        result['end_station'] = result['stations'][-1]
    
    return result

def route_question(question: str) -> Tuple[int, str, Dict[str, Any]]:
    """
    路由问题到对应的处理路径
    """
    intent = recognize_intent_with_small_model(question)
    
    entities = parse_entities(question)
    intent_name = get_intent_name(intent)
    
    print(f"[DEBUG] 意图识别结果: {intent_name}")
    
    return (intent, intent_name, entities)
