"""
意图识别模块 - 纯大模型识别
根据GPT建议优化：强提示词 + 多示例 + 判断优先级 + num_predict=1 + 二次纠正
"""

from typing import Tuple, Dict, Any
import re

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
    INTENT_KNOWLEDGE: "非结构化知识查询",
    INTENT_CHAT: "闲聊"
}


def get_intent_name(intent: int) -> str:
    """获取意图名称"""
    return INTENT_NAMES.get(intent, "未知")


def recognize_intent_with_model(question: str, llm) -> int:
    """
    使用大模型进行意图识别 - 纯模型识别
    根据GPT建议优化：强提示词 + 多示例 + 判断优先级 + 二次纠正
    """
    if not question or not question.strip():
        return INTENT_CHAT
    
    # 主提示词 - 强提示词版本
    main_prompt = f"""你是轨道交通智能问答系统中的"意图识别模块"。
你的任务只有一个：判断用户问题属于哪一类意图。
注意：你不是问答助手，不能回答用户问题，不能解释原因。

请从下面6个类别中选择最合适的一个：

1 = 站点信息查询
含义：用户询问某一个站点的基本信息、位置、设施、换乘线路等。
示例：
S1站在哪里
S2是什么站
S3属于哪条线路
介绍一下S5站
S1站的信息
哪个站可以换乘L2线
S7站有什么设施
S10站的位置

2 = 线路信息查询
含义：用户询问某一条线路的基本信息、站点列表、首末班车时间、运行情况等。
示例：
L1线路有哪些站
1号线经过哪些站
L2首班车几点
L3末班车几点
介绍一下2号线
一号线的站点列表
L5线首末班车时间
二号线有多少个站

3 = 客流数据分析
含义：用户询问客流量、人流量、进出站人数、拥挤程度、客流变化、预测或统计等。
示例：
今天客流量是多少
S1昨天进站人数
哪一站人最多
早高峰客流怎么样
预测明天客流
上周客流变化趋势
S5站客流数据
哪个站客流量最大
进站人数统计
客流最少的站

4 = 线路推荐
含义：用户询问从一个站点到另一个站点怎么走、如何乘车、路线规划、换乘方案等。
示例：
S1到S10怎么走
从S2去S8
S3到S6坐什么线
从A站到B站怎么换乘
帮我规划路线
S5到S9最佳路线
怎么从S1到S10
从这里到S7怎么去

5 = 知识查询
含义：用户询问轨道交通相关知识、乘车规则、安全规定、故障处理、应急措施、行李规定、设施使用、票务问题等。
示例：
车门故障怎么办
乘车有什么规定
发生火灾怎么办
票卡丢了怎么办
轨道交通安全知识
遇到突发情况怎么处理
行李重量限制
禁止携带物品
安全须知
故障处理流程
车门故障咋办
电梯坏了怎么办
如何购买车票
退票规则是什么

6 = 闲聊
含义：问候、感谢、告别、自我介绍、无关问题，或者不属于轨道交通业务范围的问题。
示例：
你好
谢谢
再见
你是谁
今天天气怎么样
讲个笑话
你好呀
感谢你的帮助
明天天气

仔细阅读每个类别的定义和示例，根据用户问题的语义判断最合适的意图类别。

输出要求（必须严格遵守）：
- 只能输出一个数字：1、2、3、4、5、6
- 不要输出任何解释、说明或标点
- 不要输出句子或回答问题
- 只输出数字

用户问题：{question}
意图编号："""

    # 二次纠正提示词
    retry_prompt = f"""格式错误！请重新判断。
只能输出 1、2、3、4、5、6 中的一个数字。
不要解释，不要回答问题。

用户问题：{question}
意图编号："""

    def extract_intent(response_str):
        """从响应中提取意图数字"""
        match = re.search(r'(\d+)', response_str)
        if match:
            intent_num = int(match.group(1))
            if intent_num in INTENT_NAMES:
                return intent_num
        return None

    try:
        # 第一次调用
        print("[DEBUG] 意图识别 - 第一次调用模型...")
        response = llm.invoke(main_prompt)
        
        if hasattr(response, 'content'):
            response_str = response.content.strip()
        elif isinstance(response, str):
            response_str = response.strip()
        else:
            response_str = str(response).strip()
        
        print(f"[DEBUG] 第一次返回: {response_str}")
        
        intent = extract_intent(response_str)
        if intent:
            return intent
        
        # 第二次纠正调用
        print("[DEBUG] 意图识别 - 格式错误，进行二次纠正...")
        response = llm.invoke(retry_prompt)
        
        if hasattr(response, 'content'):
            response_str = response.content.strip()
        elif isinstance(response, str):
            response_str = response.strip()
        else:
            response_str = str(response).strip()
        
        print(f"[DEBUG] 第二次返回: {response_str}")
        
        intent = extract_intent(response_str)
        if intent:
            return intent
        
        # 两次都失败，返回知识查询作为兜底
        return INTENT_KNOWLEDGE
        
    except Exception as e:
        print(f"[ERROR] 大模型意图识别失败: {e}")
        return INTENT_KNOWLEDGE


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


def route_question(question: str, llm=None) -> Tuple[int, str, Dict[str, Any]]:
    """
    路由问题到对应的处理路径
    """
    if llm:
        intent = recognize_intent_with_model(question, llm)
    else:
        intent = INTENT_KNOWLEDGE
    
    entities = parse_entities(question)
    intent_name = get_intent_name(intent)
    
    return (intent, intent_name, entities)
