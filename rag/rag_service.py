"""
总结服务类：用户提问，搜索参考资料，将提问和参考资料提交给模型，让模型总结回复
包含 RAG 链路的高阶优化：Query Rewrite 与 LLM-as-a-Reranker
"""
import re
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser

from rag.vector_store import VectorStoreService
from utils.prompt_loader import load_rag_prompts
from langchain_core.prompts import PromptTemplate
from model.factory import chat_model
from utils.logger_handler import logger


def print_prompt(prompt):
    logger.debug("="*20)
    logger.debug(prompt.to_string())
    logger.debug("="*20)
    return prompt


class RagSummarizeService(object):
    def __init__(self, enable_rewrite: bool = True, enable_rerank: bool = True):
        self.vector_store = VectorStoreService()
        self.enable_rewrite = enable_rewrite
        self.enable_rerank = enable_rerank
        
        # 如果开启重排，我们先粗排召回 Top-15
        initial_k = 15 if self.enable_rerank else 5
        self.retriever = self.vector_store.get_retriever(search_kwargs={"k": initial_k})
        
        self.prompt_text = load_rag_prompts()
        self.prompt_template = PromptTemplate.from_template(self.prompt_text)
        self.model = chat_model
        self.chain = self._init_chain()

    def _init_chain(self):
        chain = self.prompt_template | print_prompt | self.model | StrOutputParser()
        return chain

    def _rewrite_query(self, original_query: str) -> str:
        """查询重写：利用大模型提取和扩写口语化的 Query"""
        prompt = f"你是一个搜索引擎优化专家。请提取出以下用户的核心搜索意图，将其改写为一个能直接用于向量数据库检索的精准专业名词短语（消除口语化）。\n用户原始问题：{original_query}\n请只输出重写后的短语，不要有任何多余解释："
        try:
            resp = self.model.invoke(prompt)
            rewritten = resp.content.strip()
            logger.info(f"[RAG] 查询重写: '{original_query}' -> '{rewritten}'")
            return rewritten
        except Exception as e:
            logger.error(f"[RAG] 查询重写失败: {e}")
            return original_query

    def _llm_rerank(self, query: str, docs: list[Document], top_k: int = 5) -> list[Document]:
        """LLM-as-a-Reranker: 让大模型做 Listwise 交叉打分重排"""
        if not docs:
            return []
            
        prompt = f"你是一个内容相关性排序专家。请根据用户的查询意图：'{query}'，从以下检索到的候选文档片段中挑选出最相关的 {top_k} 个片段的编号。\n\n候选片段：\n"
        for i, doc in enumerate(docs):
            # 截断文档防止过长
            content_preview = doc.page_content.replace('\n', ' ')[:150]
            prompt += f"[{i}] {content_preview}...\n"
            
        prompt += f"\n请直接输出高度相关的文档编号列表，按相关度从高到低排序，以逗号分隔（例如：3, 0, 7）。不要输出任何其他解释性文字。"
        
        try:
            resp = self.model.invoke(prompt).content.strip()
            # 用正则提取所有数字
            indices = [int(idx) for idx in re.findall(r'\d+', resp)]
            logger.info(f"[RAG] 粗排数量 {len(docs)}，LLM重排选出的编号: {indices}")
            
            # 根据提取的索引重新组装 Docs
            reranked_docs = []
            seen = set()
            for idx in indices:
                if idx < len(docs) and idx not in seen:
                    reranked_docs.append(docs[idx])
                    seen.add(idx)
                    if len(reranked_docs) >= top_k:
                        break
                        
            # 如果大模型啥也没提取出来，就退化为原始 TopK
            return reranked_docs if reranked_docs else docs[:top_k]
        except Exception as e:
            logger.error(f"[RAG] LLM 重排失败: {e}")
            return docs[:top_k]

    def retriever_docs(self, query: str) -> list[Document]:
        search_query = query
        if self.enable_rewrite:
            search_query = self._rewrite_query(query)
            
        # 混合粗排：语义向量召回 + 中文关键词召回。
        vector_docs = self.retriever.invoke(search_query)
        keyword_docs = self.vector_store.keyword_search(query, k=10)

        docs = []
        seen = set()
        for doc in keyword_docs + vector_docs:
            identity = (
                doc.metadata.get("source"),
                doc.metadata.get("chunk_index"),
                doc.page_content,
            )
            if identity not in seen:
                docs.append(doc)
                seen.add(identity)
        
        # 精排重排
        if self.enable_rerank and len(docs) > 5:
            docs = self._llm_rerank(query, docs, top_k=5)
            
        return docs

    def rag_summarize(self, query: str) -> str:

        context_docs = self.retriever_docs(query)

        context = ""
        counter = 0
        for doc in context_docs:
            counter += 1
            context += f"【参考资料{counter}】: 参考资料：{doc.page_content} | 参考元数据：{doc.metadata}\n"

        return self.chain.invoke(
            {
                "input": query,
                "context": context,
            }
        )


if __name__ == '__main__':
    rag = RagSummarizeService()
    print(rag.rag_summarize("小户型适合哪些扫地机器人"))
