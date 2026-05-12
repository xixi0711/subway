"""
RAG知识库模块 - 使用 FAISS 向量数据库
"""

import os
import re
from typing import List, Dict, Any

# 禁用 Hugging Face 网络访问，强制使用本地缓存
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'

# 全局变量
_vector_db = None
_embedding = None
_initialized = False


def _init():
    """初始化向量数据库和嵌入模型（只执行一次）"""
    global _vector_db, _embedding, _initialized
    
    if _initialized:
        return
    
    try:
        from langchain_community.vectorstores import FAISS
        from langchain_community.embeddings import HuggingFaceEmbeddings
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from langchain.schema import Document
        
        print("[RAG] 正在初始化向量数据库...")
        
        # 1. 初始化嵌入模型 - 优先使用本地缓存
        print("[RAG] 正在加载嵌入模型...")
        
        # 检查本地缓存
        user_profile = os.environ.get('USERPROFILE', '')
        cache_path = os.path.join(user_profile, '.cache', 'huggingface', 'hub', 'models--BAAI--bge-small-zh')
        
        if os.path.exists(cache_path):
            print(f"[RAG] 使用本地缓存模型: {cache_path}")
            _embedding = HuggingFaceEmbeddings(model_name="BAAI/bge-small-zh")
        else:
            print("[RAG] 下载嵌入模型...")
            _embedding = HuggingFaceEmbeddings(model_name="BAAI/bge-small-zh")
        
        print("[RAG] 嵌入模型加载完成")
        
        # 2. 检查是否有已保存的向量库
        if os.path.exists("vector_db"):
            print("[RAG] 正在加载已保存的向量库...")
            _vector_db = FAISS.load_local("vector_db", _embedding, allow_dangerous_deserialization=True)
            print("[RAG] 向量库加载完成")
        else:
            print("[RAG] 未找到向量库，需要先构建")
            _vector_db = None
        
        _initialized = True
        
    except Exception as e:
        print(f"[RAG] 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        _vector_db = None
        _initialized = False


def build_knowledge_base(directory: str = "./knowledge_base") -> int:
    """从目录构建知识库（纯段落级）"""
    global _vector_db, _embedding, _initialized
    
    # 确保初始化（但不是在导入时）
    if not _initialized:
        try:
            _init()
        except Exception as e:
            print(f"[RAG] 初始化失败: {e}")
            return 0
    
    from langchain_community.vectorstores import FAISS
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from langchain.schema import Document
    
    # 段落级文档列表
    paragraph_docs = []
    
    if not os.path.exists(directory):
        print(f"[RAG] 目录不存在: {directory}")
        return 0
    
    # 加载所有文档并按段落分割
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        if os.path.isfile(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 按段落分割（空行分隔）
                paragraphs = re.split(r'\n\n+', content)
                
                for i, paragraph in enumerate(paragraphs):
                    paragraph = paragraph.strip()
                    if len(paragraph) < 10:
                        continue
                    
                    doc = Document(
                        page_content=paragraph,
                        metadata={"source": filename, "paragraph": i+1}
                    )
                    paragraph_docs.append(doc)
                
                print(f"[RAG] 已加载: {filename} (分割为 {len(paragraphs)} 个段落)")
            except Exception as e:
                print(f"[RAG] 加载文件 {filename} 失败: {e}")
    
    if not paragraph_docs:
        print("[RAG] 没有找到可加载的段落")
        return 0
    
    print(f"[RAG] 共 {len(paragraph_docs)} 个段落")
    
    # 创建向量库（每个段落作为独立向量）
    print("[RAG] 正在创建段落级向量库...")
    
    if _embedding is None:
        _embedding = HuggingFaceEmbeddings(model_name="BAAI/bge-small-zh")
    
    _vector_db = FAISS.from_documents(paragraph_docs, _embedding)
    
    # 保存向量库
    print("[RAG] 正在保存向量库...")
    _vector_db.save_local("vector_db")
    
    _initialized = True
    print(f"[RAG] 知识库构建完成，共 {len(paragraph_docs)} 个段落")
    
    return len(paragraph_docs)


def add_knowledge(content: str, metadata: Dict[str, Any] = None) -> bool:
    """添加单条知识"""
    from langchain.schema import Document
    
    _init()
    
    if _vector_db is None:
        return False
    
    if metadata is None:
        metadata = {}
    
    doc = Document(page_content=content, metadata=metadata)
    _vector_db.add_documents([doc])
    _vector_db.save_local("vector_db")
    return True


def retrieve_knowledge(query: str, k: int = 3) -> List[Dict[str, Any]]:
    """检索知识"""
    # 第一次使用时才初始化
    if not _initialized:
        try:
            _init()
        except Exception as e:
            print(f"[RAG] 初始化失败: {e}")
            return []
    
    if _vector_db is None:
        return []
    
    results = _vector_db.similarity_search_with_score(query, k=k)
    
    retrieved = []
    for doc, score in results:
        retrieved.append({
            "content": doc.page_content,
            "metadata": doc.metadata,
            "score": float(score)
        })
    
    return retrieved


# 同义词映射表 - 用于增强检索效果
SYNONYMS = {
    "包裹": ["行李", "物品", "行李物品", "包裹行李"],
    "行李": ["包裹", "物品", "行李物品", "包裹行李"],
    "体积": ["尺寸", "大小", "长宽高", "尺寸要求", "大小限制"],
    "长宽高": ["体积", "尺寸", "大小", "尺寸要求"],
    "重量": ["重量限制", "重量要求", "最大重量"],
    "尺寸": ["体积", "长宽高", "大小", "尺寸要求"],
    "禁止": ["不允许", "不准", "严禁", "不可"],
    "安全": ["安保", "安检", "安全检查"],
    "乘车": ["乘坐", "搭乘", "坐地铁"],
    "换乘": ["转乘", "换乘站", "转车"],
}

def expand_query_with_synonyms(query: str) -> str:
    """使用同义词扩展查询，提高检索召回率"""
    expanded_terms = [query]
    
    for word, synonyms in SYNONYMS.items():
        if word in query:
            for synonym in synonyms:
                if synonym not in query and synonym not in expanded_terms:
                    expanded_terms.append(synonym)
    
    return " ".join(expanded_terms)


def get_retrieval_context(query: str, k: int = 3) -> str:
    """获取检索上下文，用于增强prompt（纯段落级检索）"""
    # 第一次使用时才初始化
    if not _initialized:
        try:
            _init()
        except Exception as e:
            print(f"[RAG] 初始化失败，跳过检索: {e}")
            return ""
    
    if not _initialized or _vector_db is None:
        print(f"[RAG] RAG 未初始化，跳过检索")
        return ""
    
    # 使用同义词扩展查询，提高召回率
    expanded_query = expand_query_with_synonyms(query)
    print(f"[RAG] 原始查询: {query}")
    print(f"[RAG] 扩展查询: {expanded_query}")
    
    # 先使用扩展查询进行检索
    results = retrieve_knowledge(expanded_query, k=k)
    
    # 如果扩展查询没有结果，使用原始查询
    if not results:
        results = retrieve_knowledge(query, k=k)
    
    if not results:
        print(f"[RAG] 未检索到相关知识: {query}")
        return ""
    
    print(f"[RAG] 检索到 {len(results)} 个相关段落")
    
    context = "相关知识参考：\n"
    total_length = 0
    used_sources = set()
    
    for i, result in enumerate(results, 1):
        score = result['score']
        content = result['content']
        source = result['metadata'].get('source', 'unknown')
        paragraph = result['metadata'].get('paragraph', 0)
        
        # 段落级相似度阈值过滤
        if score < 0.3:
            print(f"[RAG] 跳过段落{i} - 相似度: {score:.4f} (低于阈值0.3)")
            continue
        
        print(f"[RAG] 段落{i} - 语义相似度: {score:.4f}, 来源: {source} 第{paragraph}段")
        
        # 添加到上下文
        if source not in used_sources:
            context += f"\n【{source}】\n"
            used_sources.add(source)
        
        context += f"{content}\n"
        total_length += len(content)
    
    if total_length == 0:
        print(f"[RAG] 没有找到相似度高于0.3的段落")
        return ""
    
    print(f"[RAG] 最终上下文长度: {total_length} 字")
    
    return context


# 立即初始化 - 在模块导入时就初始化向量数据库
# 避免第一次请求时的长时间加载
_init()

def preload_rag():
    """预加载RAG向量数据库（在应用启动时调用）"""
    global _initialized
    if not _initialized:
        _init()
    print("[RAG] RAG知识库预加载完成")
