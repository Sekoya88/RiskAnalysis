"""Infrastructure — ChromaDB Vector Store adapter."""

from __future__ import annotations

import glob
import os
import re
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.domain.ports.embeddings import EmbeddingPort


class ChromaVectorStoreAdapter:
    """VectorStorePort implementation backed by ChromaDB.

    Lazily initializes and seeds from PDF documents on first access.
    """

    def __init__(
        self,
        embedding: EmbeddingPort,
        persist_directory: str,
        collection_name: str = "corporate_disclosures",
        docs_directory: str | None = None,
    ):
        self._embedding = embedding
        self._persist_directory = persist_directory
        self._collection_name = collection_name
        self._docs_directory = docs_directory
        self._store: Chroma | None = None

    def _get_store(self) -> Chroma:
        if self._store is None:
            self._store = Chroma(
                collection_name=self._collection_name,
                embedding_function=self._embedding,
                persist_directory=self._persist_directory,
            )
            existing = self._store.get()
            if len(existing.get("ids", [])) == 0 and self._docs_directory:
                docs = self._load_local_docs()
                if docs:
                    self._store.add_documents(docs)
        return self._store

    def _load_local_docs(self) -> list[Document]:
        """Scan docs directory for PDFs, load and split into chunks."""
        if not self._docs_directory:
            return []

        pdf_files = glob.glob(os.path.join(self._docs_directory, "*.pdf"))
        if not pdf_files:
            return []

        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        all_docs: list[Document] = []

        for pdf_path in pdf_files:
            try:
                loader = PyPDFLoader(pdf_path)
                docs = loader.load_and_split(text_splitter=splitter)

                filename = os.path.basename(pdf_path)
                company = "Global"
                company_match = re.search(r"([A-Z][a-z]+)", filename)
                if company_match:
                    potential = company_match.group(1)
                    if not any(kw in filename.lower() for kw in ["risks", "outlook", "wef", "fitch", "global"]):
                        company = potential

                for doc in docs:
                    doc.metadata["source"] = filename
                    doc.metadata["company"] = company
                    doc.metadata["type"] = "pdf_report"

                all_docs.extend(docs)
            except Exception:
                pass

        return all_docs

    def similarity_search(self, query: str, k: int = 5, filter: dict | None = None) -> list[Document]:
        return self._get_store().similarity_search(query=query, k=k, filter=filter)

    def add_documents(self, documents: list[Any]) -> None:
        self._get_store().add_documents(documents)

    def get(self, include: list[str] | None = None) -> dict:
        kwargs = {}
        if include:
            kwargs["include"] = include
        return self._get_store().get(**kwargs)
