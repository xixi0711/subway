#!/usr/bin/env python3
"""
完整的LangChain Agent实现
让LLM自己决定用哪个工具进行查询
"""
import os
import sqlite3
from dotenv import load_dotenv
from langchain_community.llms import Ollama
from langchain_community.utilities import SQLDatabase
from langchain.agents import create_sql_agent
from langchain.agents.agent_types import AgentType
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain.chains import RetrievalQA
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.tools import Tool
from langchain.agents import initialize_agent
from langchain.prompts import SystemMessagePromptTemplate, HumanMessagePromptTemplate, ChatPromptTemplate

load_dotenv()

class LangChainAgent:
    def __init__(self):
        # 1. 初始化LLM（支持Ollama和外部API）
        use_ollama = os.environ.get("USE_OLLAMA", "false").lower() == "true"
        
        if use_ollama:
            # 本地模型 - Ollama
            self.llm = Ollama(model=os.environ.get("OLLAMA_MODEL", "qwen:7b"), temperature=0.1)
            print(f"[LangChain Agent] LLM初始化完成: Ollama - {os.environ.get('OLLAMA_MODEL', 'qwen:7b')}")
        else:
            # 外部API - 火山引擎
            from langchain_openai import ChatOpenAI
            
            # 移除URL末尾的 /chat/completions，因为ChatOpenAI会自动添加
            base_url = os.environ.get("ARK_API_URL", "").rstrip("/chat/completions").rstrip("/")
            
            self.llm = ChatOpenAI(
                model=os.environ.get("MODEL_NAME"),
                api_key=os.environ.get("ARK_API_KEY"),
                base_url=base_url,
                temperature=0.1
            )
            print(f"[LangChain Agent] LLM初始化完成: 外部API - {os.environ.get('MODEL_NAME')}")
        
        # 2. 初始化SQL数据库
        self.db = SQLDatabase.from_uri("sqlite:///subway.db")
        self.sql_toolkit = SQLDatabaseToolkit(db=self.db, llm=self.llm)
        print("[LangChain Agent] SQL数据库初始化完成")
        
        # 3. 初始化RAG（带错误处理）
        self.embedding = None
        self.vector_db = None
        self.rag_enabled = True
        try:
            print("[LangChain Agent] 正在加载嵌入模型...")
            
            # 优先使用本地缓存路径
            cache_path = os.path.join(os.environ.get("USERPROFILE"), ".cache", "huggingface", "hub", "models--BAAI--bge-small-zh")
            if os.path.exists(cache_path):
                print(f"[LangChain Agent] 发现缓存路径: {cache_path}")
                
                # 查找有效的snapshot目录
                snapshots_dir = os.path.join(cache_path, "snapshots")
                if os.path.exists(snapshots_dir):
                    snapshots = [d for d in os.listdir(snapshots_dir) if os.path.isdir(os.path.join(snapshots_dir, d))]
                    if snapshots:
                        local_model_path = os.path.join(snapshots_dir, snapshots[0])
                        print(f"[LangChain Agent] 使用本地模型: {local_model_path}")
                        self.embedding = HuggingFaceEmbeddings(model_name=local_model_path)
                    else:
                        self.embedding = HuggingFaceEmbeddings(model_name="BAAI/bge-small-zh")
                else:
                    self.embedding = HuggingFaceEmbeddings(model_name="BAAI/bge-small-zh")
            else:
                self.embedding = HuggingFaceEmbeddings(model_name="BAAI/bge-small-zh")
            
            print("[LangChain Agent] 嵌入模型加载完成")
            
            print("[LangChain Agent] 正在加载FAISS向量库...")
            self.vector_db = FAISS.load_local("vector_db", self.embedding, allow_dangerous_deserialization=True)
            print("[LangChain Agent] RAG知识库初始化完成")
        except Exception as e:
            print(f"[LangChain Agent] RAG初始化失败，将禁用RAG功能: {e}")
            self.rag_enabled = False
        
        # 4. 创建工具列表
        self._create_tools()
        
        # 5. 创建Agent
        self._create_agent()
        
    def _create_tools(self):
        """创建工具列表"""
        # 数据库结构说明（中文表名和字段）
        db_schema_info = """
数据库包含以下表：

1. 线路信息表（线路信息）：
   - 线路编号：线路的唯一标识
   - 线路名称：线路名称（如"一号线"）
   - 首班车时间：首班车发车时间
   - 末班车时间：末班车发车时间

2. 站点信息表（站点信息）：
   - 站点编号：站点的唯一标识（如"S1"）
   - 所属线路编号：站点所属的线路
   - 站点名称：站点名称
   - x坐标、y坐标：站点位置

3. 列车时刻表（列车时刻）：
   - 列车编号：列车的唯一标识
   - 所属线路编号：列车所属线路
   - 途经站点编号：途经的站点
   - 到站时间、发车时间

4. 客流统计表（客流统计）：
   - 站点编号：站点标识
   - 统计日期：统计日期
   - 进站人数、出站人数、总客流

5. 换乘关系表（换乘关系）：
   - 站点编号、站点名称、所属线路

请使用中文表名进行查询！例如：SELECT * FROM 线路信息表 WHERE 线路名称='一号线'
"""
        
        # SQL查询工具
        from langchain.agents import create_sql_agent
        from langchain.agents.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
        
        # 创建自定义提示词
        from langchain.prompts import PromptTemplate
        
        sql_agent_prompt = """
你是一个专业的SQL查询助手。你可以访问一个包含地铁信息的SQLite数据库。

数据库表结构：
{db_schema}

请根据用户的问题，生成正确的SQL查询语句。

注意事项：
1. 必须使用中文表名和中文字段名
2. SQLite语法，不需要引号包裹表名和字段名
3. 查询结果会返回给你，由你用自然语言总结

用户问题：{{input}}
"""
        
        sql_agent = create_sql_agent(
            llm=self.llm,
            toolkit=self.sql_toolkit,
            agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,
            handle_parsing_errors=True,
            agent_kwargs={
                "system_prompt": sql_agent_prompt.format(db_schema=db_schema_info)
            }
        )
        
        # 定义工具列表
        self.tools = [
            Tool(
                name="SQL查询工具",
                func=sql_agent.run,
                description="用于查询地铁数据库中的结构化数据，例如：站点数量、线路信息、首末班车时间、站点位置等。当用户询问具体的数据时使用此工具。"
            ),
            Tool(
                name="路线规划工具",
                func=self._route_planning,
                description="用于查询两个站点之间的最优路线和换乘方案。当用户询问从一个站点到另一个站点的路线时使用此工具。"
            )
        ]
        
        # RAG检索工具（仅在RAG启用时添加）
        if self.rag_enabled and self.vector_db:
            rag_chain = RetrievalQA.from_chain_type(
                llm=self.llm,
                chain_type="stuff",
                retriever=self.vector_db.as_retriever(search_kwargs={"k": 3}),
                verbose=True
            )
            self.tools.append(
                Tool(
                    name="知识库检索工具",
                    func=rag_chain.run,
                    description="用于查询地铁相关的非结构化知识，例如：故障处理流程、乘车须知、安全规定等。当用户询问操作指南、处理流程时使用此工具。"
                )
            )
            print("[LangChain Agent] RAG工具已添加")
        else:
            print("[LangChain Agent] RAG工具未添加（RAG未启用）")
        
    def _route_planning(self, query):
        """路线规划工具"""
        station_list = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6', 'S7', 'S8', 'S9', 'S10']
        found_stations = [s for s in station_list if s in query]
        
        if len(found_stations) < 2:
            return "请提供起点和终点站点"
            
        start_station, end_station = found_stations[0], found_stations[-1]
        
        conn = sqlite3.connect('subway.db')
        cursor = conn.cursor()
        cursor.execute("SELECT 站点编号, 所属线路编号 FROM 站点信息表")
        station_lines = {}
        for row in cursor.fetchall():
            station_lines[row[0]] = row[1].split(',') if row[1] else []
        conn.close()
        
        if start_station not in station_lines or end_station not in station_lines:
            return "无法找到指定的站点"
            
        start_line_set = set(station_lines[start_station])
        end_line_set = set(station_lines[end_station])
        
        common_lines = start_line_set & end_line_set
        if common_lines:
            return f"从{start_station}到{end_station}可以直接乘坐{','.join(common_lines)}线直达"
        
        conn = sqlite3.connect('subway.db')
        cursor = conn.cursor()
        cursor.execute("SELECT 站点编号, 所属线路编号, 站点名称 FROM 站点信息表")
        for row in cursor.fetchall():
            station = row[0]
            station_name = row[2]
            if station == start_station or station == end_station:
                continue
            lines = set(row[1].split(',')) if row[1] else set()
            if start_line_set & lines and lines & end_line_set:
                line1 = list(start_line_set & lines)[0]
                line2 = list(end_line_set & lines)[0]
                return f"从{start_station}乘坐{line1}线到{station}（{station_name}）换乘{line2}线，然后到达{end_station}"
        conn.close()
        
        return f"抱歉，无法找到从{start_station}到{end_station}的路线"
    
    def _create_agent(self):
        """创建主Agent"""
        # 系统提示词
        system_prompt = """
你是一个专业的地铁智能问答助手。你可以使用以下工具来回答用户的问题：

可用工具：
1. SQL查询工具：用于查询结构化数据，如站点数量、线路信息、时刻表等
2. 知识库检索工具：用于查询非结构化知识，如故障处理、乘车须知等
3. 路线规划工具：用于查询站点间的最优路线和换乘方案

请仔细分析用户的问题，选择最合适的工具。

回答要求：
- 如果需要使用工具，请使用工具获取信息后再回答
- 如果不需要工具，可以直接回答
- 回答要友好、清晰、准确
"""
        
        # 创建Agent
        self.agent = initialize_agent(
            tools=self.tools,
            llm=self.llm,
            agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            verbose=True,
            handle_parsing_errors=True,
            agent_kwargs={
                "system_prompt": system_prompt
            }
        )
        
        print("[LangChain Agent] 初始化完成")
    
    def query(self, question):
        """执行查询"""
        try:
            print(f"[LangChain Agent] 开始处理问题: {question}")
            result = self.agent.run(question)
            print(f"[LangChain Agent] 回答: {result}")
            return result
        except Exception as e:
            print(f"[LangChain Agent] 错误类型: {type(e).__name__}")
            print(f"[LangChain Agent] 错误信息: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # 如果是RAG相关错误，尝试直接使用模型回答
            if self.rag_enabled:
                try:
                    print("[LangChain Agent] 尝试直接使用LLM回答...")
                    prompt = f"请回答以下问题：{question}"
                    result = self.llm(prompt)
                    print(f"[LangChain Agent] LLM直接回答: {result}")
                    return result
                except Exception as e2:
                    print(f"[LangChain Agent] LLM直接回答也失败: {e2}")
            
            return f"查询失败: {str(e)}"
    
    def get_status(self):
        """获取状态"""
        tools = ["SQL查询工具", "路线规划工具"]
        if self.rag_enabled:
            tools.append("知识库检索工具")
        
        return {
            "type": "LangChain Agent",
            "llm": "Ollama",
            "model": os.environ.get("OLLAMA_MODEL", "qwen:7b"),
            "tools": tools,
            "database": "SQLite",
            "rag_enabled": self.rag_enabled
        }

# 全局实例
_agent_instance = None

def get_agent():
    """获取全局Agent实例"""
    global _agent_instance
    if _agent_instance is None:
        _agent_instance = LangChainAgent()
    return _agent_instance

if __name__ == "__main__":
    agent = get_agent()
    print(f"Agent状态: {agent.get_status()}")
    
    print("\n" + "="*60)
    print("测试问题：一号线有几个站点？")
    result = agent.query("一号线有几个站点？")
    print(f"最终回答: {result}")
