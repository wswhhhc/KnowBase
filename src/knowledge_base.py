"""知识库管理模块：文档加载、分割、嵌入存储、混合检索、重排序"""

import os
from typing import List, Optional, Tuple
from pathlib import Path

from langchain_core.documents import Document
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from rank_bm25 import BM25Okapi

from config.settings import (
    SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL,
    EMBEDDING_MODEL, CHROMA_PERSIST_DIR,
    CHUNK_SIZE, CHUNK_OVERLAP,
    TOP_K_RETRIEVAL, BM25_WEIGHT, VECTOR_WEIGHT, DATA_DIR,
)


class KnowledgeBase:
    """知识库，管理文档的加载、存储和检索"""

    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            model=EMBEDDING_MODEL,
            openai_api_key=SILICONFLOW_API_KEY,
            openai_api_base=SILICONFLOW_BASE_URL,
        )
        self.vector_store = self._init_vector_store()
        self.bm25_index: Optional[BM25Okapi] = None
        self.bm25_docs: List[Document] = []
        self.all_docs: List[Document] = []

    def _init_vector_store(self) -> Chroma:
        """初始化向量数据库（持久化模式）"""
        return Chroma(
            persist_directory=CHROMA_PERSIST_DIR,
            embedding_function=self.embeddings,
            collection_name="knowbase",
        )

    def load_preset_documents(self) -> int:
        """加载 data/ 目录下的所有预设文本文档"""
        txt_files = sorted(Path(DATA_DIR).glob("sample_*.txt"))
        if not txt_files:
            return 0

        docs = []
        for file_path in txt_files:
            loader = TextLoader(str(file_path), encoding="utf-8")
            docs.extend(loader.load())

        return self._process_documents(docs)

    def _process_documents(self, docs: List[Document]) -> int:
        """分割文档并存入向量库和 BM25 索引"""
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n## ", "\n### ", "\n\n", "\n", "。"],
        )
        splits = splitter.split_documents(docs)

        if not splits:
            return 0

        # 存入 Chroma
        self.vector_store.add_documents(splits)

        # 更新 BM25 索引
        self.all_docs.extend(splits)
        self._rebuild_bm25()

        return len(splits)

    def add_document(self, file_path: str) -> int:
        """动态添加单个文档到知识库"""
        ext = Path(file_path).suffix.lower()
        if ext == ".txt":
            loader = TextLoader(file_path, encoding="utf-8")
        elif ext == ".md":
            loader = TextLoader(file_path, encoding="utf-8")
        else:
            raise ValueError(f"不支持的文件格式：{ext}")

        docs = loader.load()
        # 标记来源文件名（不含路径）
        for d in docs:
            d.metadata["source"] = Path(file_path).name
        return self._process_documents(docs)

    def _rebuild_bm25(self):
        """重建 BM25 索引"""
        tokenized = [self._tokenize(doc.page_content) for doc in self.all_docs]
        self.bm25_index = BM25Okapi(tokenized)
        self.bm25_docs = self.all_docs

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """简单中文分词（按字/词切分，适用于 BM25）"""
        import re
        # 保留中英文、数字，按空格和标点分割
        tokens = re.findall(r'[\w]+|[一-鿿]', text.lower())
        return tokens

    def hybrid_search(self, query: str, k: int = TOP_K_RETRIEVAL) -> List[Document]:
        """混合检索：向量检索 + BM25 加权融合"""
        # 向量检索
        vector_results = self.vector_store.similarity_search_with_score(query, k=k * 2)
        vector_scores = {doc.page_content: score for doc, score in vector_results}
        vector_docs_map = {doc.page_content: doc for doc, _ in vector_results}

        # BM25 检索
        query_tokens = self._tokenize(query)
        bm25_scores = self.bm25_index.get_scores(query_tokens) if self.bm25_index else []
        bm25_ranked = sorted(
            zip(self.bm25_docs, bm25_scores),
            key=lambda x: x[1], reverse=True,
        )[:k * 2]

        # 分数归一化 + 加权融合
        all_scores = {}
        if vector_scores:
            vs_max = max(vector_scores.values())
            vs_min = min(vector_scores.values())
            vs_range = vs_max - vs_min if vs_max != vs_min else 1
            for content, score in vector_scores.items():
                normalized = 1 - (score - vs_min) / vs_range  # Chroma 距离越小越好，反转
                all_scores[content] = all_scores.get(content, 0) + normalized * VECTOR_WEIGHT

        if bm25_ranked:
            bm25_max = max(s for _, s in bm25_ranked) or 1
            for doc, score in bm25_ranked:
                normalized = score / bm25_max
                all_scores[doc.page_content] = all_scores.get(doc.page_content, 0) + normalized * BM25_WEIGHT

        # 合并所有文档去重排序
        seen = set()
        merged = []
        for content, score in sorted(all_scores.items(), key=lambda x: x[1], reverse=True):
            doc = vector_docs_map.get(content) or next(
                (d for d in self.bm25_docs if d.page_content == content), None
            )
            if doc and content not in seen:
                seen.add(content)
                merged.append(doc)
            if len(merged) >= k:
                break

        return merged

    @property
    def document_count(self) -> int:
        """返回入库的文档片段数"""
        return len(self.all_docs)

    def clear(self):
        """清空知识库"""
        self.vector_store.delete_collection()
        self.vector_store = self._init_vector_store()
        self.bm25_index = None
        self.bm25_docs = []
        self.all_docs = []
