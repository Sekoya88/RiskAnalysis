"""Infrastructure — pgvector Vector Store adapter.

Uses PostgreSQL with the pgvector extension as the vector store,
replacing ChromaDB. Runs as a service in the same PostgreSQL instance
used for reports and feedback.

Requires:
  - PostgreSQL with pgvector extension (docker: pgvector/pgvector:pg17)
  - psycopg[binary]
"""

from __future__ import annotations

import glob
import json
import os
import re
from typing import Any

import psycopg
from psycopg.rows import dict_row

from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.domain.ports.embeddings import EmbeddingPort


def _get_dsn() -> str:
    return os.getenv("DATABASE_URL", "postgresql://risk:riskpass@localhost:5432/riskanalysis")


class PgVectorStoreAdapter:
    """VectorStorePort implementation backed by PostgreSQL + pgvector.

    Stores document chunks with vector embeddings in a single table.
    Supports similarity search via cosine distance (<=> operator).
    """

    def __init__(
        self,
        embedding: EmbeddingPort,
        dsn: str | None = None,
        table_name: str = "document_embeddings",
        docs_directory: str | None = None,
    ):
        self._embedding = embedding
        self._dsn = dsn or _get_dsn()
        self._table_name = table_name
        self._docs_directory = docs_directory
        self._initialized = False

    def _ensure_table(self) -> None:
        if self._initialized:
            return

        with psycopg.connect(self._dsn) as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self._table_name} (
                    id SERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    metadata JSONB DEFAULT '{{}}',
                    embedding vector
                )
            """)
            # Create HNSW index for fast cosine similarity
            conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self._table_name}_embedding
                ON {self._table_name}
                USING hnsw (embedding vector_cosine_ops)
            """)
            conn.commit()

        self._initialized = True

        # Seed with local docs if table is empty
        count = self._count()
        if count == 0 and self._docs_directory:
            docs = self._load_local_docs()
            if docs:
                self.add_documents(docs)

    def _count(self) -> int:
        with psycopg.connect(self._dsn) as conn:
            row = conn.execute(f"SELECT COUNT(*) FROM {self._table_name}").fetchone()
            return row[0] if row else 0

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

    def add_documents(self, documents: list[Any]) -> None:
        """Embed and insert documents into pgvector."""
        self._ensure_table()

        texts = [doc.page_content for doc in documents]
        metadatas = [doc.metadata if hasattr(doc, "metadata") else {} for doc in documents]

        # Batch embed
        batch_size = 50
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_meta = metadatas[i:i + batch_size]
            embeddings = self._embedding.embed_documents(batch_texts)

            with psycopg.connect(self._dsn) as conn:
                for text, meta, emb in zip(batch_texts, batch_meta, embeddings):
                    conn.execute(
                        f"INSERT INTO {self._table_name} (content, metadata, embedding) VALUES (%s, %s, %s::vector)",
                        (text, json.dumps(meta), str(emb)),
                    )
                conn.commit()

    def similarity_search(self, query: str, k: int = 5, filter: dict | None = None) -> list[Document]:
        """Search by cosine similarity using pgvector <=> operator."""
        self._ensure_table()

        query_embedding = self._embedding.embed_query(query)

        # Build WHERE clause from filter
        where_clause = ""
        params: list[Any] = [str(query_embedding), k]

        if filter and "$or" in filter:
            conditions = []
            for cond in filter["$or"]:
                for key, value in cond.items():
                    conditions.append(f"metadata->>'{key}' = %s")
                    params.insert(-1, value)  # Insert before k
            if conditions:
                where_clause = "WHERE (" + " OR ".join(conditions) + ")"

        query_sql = f"""
            SELECT content, metadata, embedding <=> %s::vector AS distance
            FROM {self._table_name}
            {where_clause}
            ORDER BY distance ASC
            LIMIT %s
        """

        results: list[Document] = []
        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            rows = conn.execute(query_sql, params).fetchall()
            for row in rows:
                meta = row["metadata"] if isinstance(row["metadata"], dict) else json.loads(row["metadata"] or "{}")
                results.append(Document(page_content=row["content"], metadata=meta))

        return results

    def get(self, include: list[str] | None = None) -> dict:
        """Get all documents (for BM25 index building)."""
        self._ensure_table()

        with psycopg.connect(self._dsn, row_factory=dict_row) as conn:
            rows = conn.execute(f"SELECT id, content, metadata FROM {self._table_name}").fetchall()

        ids = [str(row["id"]) for row in rows]
        documents = [row["content"] for row in rows]
        metadatas = [
            row["metadata"] if isinstance(row["metadata"], dict) else json.loads(row["metadata"] or "{}")
            for row in rows
        ]

        return {"ids": ids, "documents": documents, "metadatas": metadatas}
