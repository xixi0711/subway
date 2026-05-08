"""
意图识别模块 - 区分问题类型，走不同处理路径
1 = 结构化数据查询（线路/站点等数据库查询）
2 = 非结构化知识（规章/规范等文档检索）
3 = 闲聊/无关问题
"""

import re
from typing import Tuple, Optional, Dict


INTENT_DB_QUERY = 1
INTENT_KNOWLEDGE = 2
INTENT_CHAT = 3


DB_QUERY_PATTERNS = [
    r"(?:线路|号线|几号线).*(?:首班|末班|时间|时刻表)",
    r"(?:首班|末班|首班车|末班车).*(?:线路|号线|几号线)",
    r"(?:站点|车站|站).*(?:名称|编号|在哪|位置)",
    r"(?:换乘|转线|如何换)",
    r"(?:票价|费用|多少钱|费用多少)",
    r"(?:运行|运营|几点开|几点停)",
    r"L\d线|\d号线",
    r"S\d{1,2}站",
    r"(?:卡号|刷卡|交易|进站|出站)",
    r"(?:客流|人流|客流量|进出站|客流数据|客流统计)",
    r"(?:人多|拥挤|客流量大)",
    r"(?:客流最多|客流最少|客流排行)",
]

KNOWLEDGE_PATTERNS = [
    r"(?:故障|事故|紧急|应急|处置)",
    r"(?:规章|规范|条例|规定|准则)",
    r"(?:安全|防护|注意|须知|提示)",
    r"(?:操作|步骤|流程|如何处理|怎么处理)",
    r"(?:原因|为什么|为何)",
    r"(?:定义|概念|什么是|什么叫)",
    r"(?:行李|携带|物品|禁止携带)",
    r"(?:购票|检票|票务|票价)",
    r"(?:乘车|候车|上车|下车)",
]

CHAT_PATTERNS = [
    r"(?:你好|您好|嗨|hi|hello)",
    r"(?:谢谢|感谢|多谢)",
    r"(?:再见|拜拜|下次见)",
    r"(?:你是谁|叫什么|名字)",
    r"(?:天气|今天|明天|日期)",
    r"(?:北京|上海|广州|城市)",
    r"(?:吃饭|美食|餐厅)",
    r"(?:新闻|八卦|娱乐)",
]


def recognize_intent(question: str) -> int:
    """
    识别问题意图

    Args:
        question: 用户问题

    Returns:
        1 = 结构化数据查询（数据库）
        2 = 非结构化知识（文档检索）
        3 = 闲聊/无关问题
    """
    if not question or not question.strip():
        return INTENT_CHAT

    question_lower = question.lower()

    db_score = 0
    for pattern in DB_QUERY_PATTERNS:
        if re.search(pattern, question_lower):
            db_score += 1

    knowledge_score = 0
    for pattern in KNOWLEDGE_PATTERNS:
        if re.search(pattern, question_lower):
            knowledge_score += 1

    chat_score = 0
    for pattern in CHAT_PATTERNS:
        if re.search(pattern, question_lower):
            chat_score += 1

    if chat_score > 0 and db_score == 0 and knowledge_score == 0:
        return INTENT_CHAT

    if knowledge_score > db_score:
        return INTENT_KNOWLEDGE

    return INTENT_DB_QUERY


def get_intent_name(intent: int) -> str:
    """获取意图名称"""
    names = {
        INTENT_DB_QUERY: "结构化数据查询",
        INTENT_KNOWLEDGE: "非结构化知识查询",
        INTENT_CHAT: "闲聊/无关问题"
    }
    return names.get(intent, "未知")


def route_question(question: str) -> Tuple[int, str]:
    """
    路由问题到对应的处理路径

    Returns:
        (意图类型, 建议的处理方式)
    """
    intent = recognize_intent(question)

    if intent == INTENT_DB_QUERY:
        return intent, "将根据问题生成SQL查询数据库，获取线路/站点/时刻表等信息"
    elif intent == INTENT_KNOWLEDGE:
        return intent, "将从知识库检索相关文档，结合AI生成回答"
    else:
        return intent, "将引导用户提问地铁相关问题或进行友好对话"


def parse_db_query(question: str) -> Optional[Dict[str, str]]:
    """
    解析数据库查询问题，提取查询意图

    Returns:
        解析结果，如 {"type": "line_schedule", "line": "L1"}
    """
    question_lower = question.lower()

    line_match = re.search(r"(L\d|\d号线|(\w+)号线|(\w+)线)", question_lower)
    line = line_match.group(1) if line_match else None

    # 只匹配真正的站点编号（如S1, S10），不区分大小写
    station_match = re.search(r"s\d{1,2}", question_lower)
    station = station_match.group(0).upper() if station_match else None

    # 检查是否包含客流相关关键词
    has_passenger_flow = bool(re.search(r"客流|人流|客流量", question_lower))
    
    # 优先处理客流相关问题
    if has_passenger_flow:
        if station:
            return {"type": "passenger_flow_station", "station": station}
        elif re.search(r"最多|排行|top", question_lower):
            return {"type": "passenger_flow_top"}
        else:
            return {"type": "passenger_flow_stats"}
    elif re.search(r"首班", question_lower):
        return {"type": "first_train", "line": line}
    elif re.search(r"末班", question_lower):
        return {"type": "last_train", "line": line}
    elif re.search(r"换乘", question_lower):
        return {"type": "transfer", "line": line}
    elif re.search(r"站点|车站", question_lower):
        return {"type": "stations", "line": line}
    elif re.search(r"时刻表|时间表", question_lower):
        return {"type": "timetable", "line": line}
    elif re.search(r"票价|费用|钱", question_lower):
        return {"type": "price", "line": line}
    else:
        return {"type": "general", "line": line}
