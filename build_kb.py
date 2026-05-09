#!/usr/bin/env python3
"""
构建 RAG 知识库
"""

from rag_knowledge_base import build_knowledge_base, get_retrieval_context

print("正在构建知识库...")
count = build_knowledge_base("./knowledge_base")
print(f"知识库构建完成，共加载 {count} 个文档")

print("\n测试检索...")
test_queries = [
    "行李重量有什么要求",
    "怎么购票",
    "车门故障怎么办"
]

for query in test_queries:
    print(f"\n查询: {query}")
    context = get_retrieval_context(query, k=3)
    print(f"检索结果:\n{context}")
