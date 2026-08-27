"""
RAG Pipeline for Feedback Intelligence.
Handles document ingestion, embedding, vector storage, and retrieval.
"""
import uuid
import hashlib
from typing import List, Dict, Any, Optional, Iterator
from dataclasses import dataclass
from datetime import datetime

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_core.documents import Document

from config.settings import settings
from db.schema.models import ProductFeedback, SupportTicket


@dataclass
class RetrievedChunk:
    """A retrieved document chunk with metadata."""
    content: str
    metadata: Dict[str, Any]
    score: float
    document_id: str


class DocumentProcessor:
    """Processes documents for RAG ingestion."""
    
    def __init__(self):
        self.chunk_size = settings.rag_chunk_size
        self.chunk_overlap = settings.rag_chunk_overlap
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""
        # Remove extra whitespace
        text = " ".join(text.split())
        # Remove control characters
        text = "".join(char for char in text if ord(char) >= 32 or char in "\n\t")
        return text.strip()
    
    def create_chunks(self, text: str, metadata: Dict[str, Any]) -> List[Document]:
        """Split text into chunks with metadata."""
        cleaned = self.clean_text(text)
        if not cleaned:
            return []
        
        docs = self.splitter.create_documents([cleaned], metadatas=[metadata])
        return docs
    
    def process_feedback(self, feedback: ProductFeedback) -> List[Document]:
        """Process a feedback record into chunks."""
        text_parts = []
        if feedback.text:
            text_parts.append(feedback.text)
        if feedback.rating is not None:
            text_parts.append(f"Rating: {feedback.rating}/10")
        
        text = " ".join(text_parts)
        metadata = {
            "document_id": str(feedback.id),
            "source": feedback.source,
            "user_id": str(feedback.user_id) if feedback.user_id else None,
            "product_area": feedback.product_area,
            "sentiment": feedback.sentiment,
            "rating": feedback.rating,
            "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
            "type": "product_feedback",
        }
        return self.create_chunks(text, metadata)
    
    def process_support_ticket(self, ticket: SupportTicket) -> List[Document]:
        """Process a support ticket into chunks."""
        text_parts = []
        if ticket.subject:
            text_parts.append(f"Subject: {ticket.subject}")
        if ticket.body:
            text_parts.append(ticket.body)
        
        text = " ".join(text_parts)
        metadata = {
            "document_id": str(ticket.id),
            "source": "support_ticket",
            "user_id": str(ticket.user_id) if ticket.user_id else None,
            "category": ticket.category,
            "priority": ticket.priority,
            "status": ticket.status,
            "tags": ticket.tags,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
            "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else None,
            "type": "support_ticket",
        }
        return self.create_chunks(text, metadata)


class VectorStore:
    """Abstract vector store interface."""
    
    def add_documents(self, documents: List[Document]) -> List[str]:
        raise NotImplementedError
    
    def similarity_search(self, query: str, k: int, filter: Optional[Dict] = None) -> List[RetrievedChunk]:
        raise NotImplementedError
    
    def similarity_search_with_score(self, query: str, k: int, filter: Optional[Dict] = None) -> List[tuple]:
        raise NotImplementedError
    
    def delete_documents(self, document_ids: List[str]) -> None:
        raise NotImplementedError


class QdrantVectorStore(VectorStore):
    """Qdrant vector store implementation."""
    
    def __init__(self):
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams, Filter, FieldCondition, MatchValue
        
        self.client = QdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
        )
        self.collection_name = settings.qdrant_collection
        self.embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            openai_api_key=settings.openai_api_key,
        )
        self.vector_size = settings.embedding_dimensions
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        from qdrant_client.models import Distance, VectorParams
        
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )
    
    def add_documents(self, documents: List[Document]) -> List[str]:
        """Add documents to Qdrant."""
        from qdrant_client.models import PointStruct
        
        texts = [doc.page_content for doc in documents]
        embeddings = self.embeddings.embed_documents(texts)
        
        points = []
        for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
            point_id = doc.metadata.get("document_id", str(uuid.uuid4()))
            # Add chunk index to make unique
            point_id = f"{point_id}_{i}"
            
            points.append(PointStruct(
                id=hashlib.md5(point_id.encode()).hexdigest()[:24],
                vector=embedding,
                payload={
                    "content": doc.page_content,
                    **doc.metadata,
                }
            ))
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        return [p.id for p in points]
    
    def similarity_search(self, query: str, k: int, filter: Optional[Dict] = None) -> List[RetrievedChunk]:
        """Search for similar documents."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        query_embedding = self.embeddings.embed_query(query)
        
        qdrant_filter = None
        if filter:
            conditions = []
            for key, value in filter.items():
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))
            if conditions:
                qdrant_filter = Filter(must=conditions)
        
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            query_filter=qdrant_filter,
            limit=k,
            with_payload=True,
        )
        
        chunks = []
        for result in results:
            payload = result.payload
            chunks.append(RetrievedChunk(
                content=payload.pop("content", ""),
                metadata=payload,
                score=result.score,
                document_id=payload.get("document_id", ""),
            ))
        return chunks
    
    def similarity_search_with_score(self, query: str, k: int, filter: Optional[Dict] = None) -> List[tuple]:
        """Search with scores."""
        chunks = self.similarity_search(query, k, filter)
        return [(chunk.content, chunk.score, chunk.metadata) for chunk in chunks]
    
    def delete_documents(self, document_ids: List[str]) -> None:
        """Delete documents by ID."""
        from qdrant_client.models import Filter, FieldCondition, MatchAny
        
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[FieldCondition(key="document_id", match=MatchAny(any=document_ids))]
            ),
        )


class PgVectorStore(VectorStore):
    """pgvector store implementation (using PostgreSQL)."""
    
    def __init__(self):
        from db.connection import sync_engine
        from sqlalchemy import text
        
        self.engine = sync_engine
        self.embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            openai_api_key=settings.openai_api_key,
        )
        self._ensure_table()
    
    def _ensure_table(self):
        """Create vector table if not exists."""
        with self.engine.connect() as conn:
            conn.execute(text("""
                CREATE EXTENSION IF NOT EXISTS vector;
                CREATE TABLE IF NOT EXISTS product_feedback_chunks (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    document_id UUID NOT NULL,
                    chunk_index INT NOT NULL,
                    content TEXT NOT NULL,
                    embedding vector(1536),
                    metadata JSONB NOT NULL DEFAULT '{}',
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_feedback_chunks_embedding 
                ON product_feedback_chunks USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
                CREATE INDEX IF NOT EXISTS idx_feedback_chunks_doc_id 
                ON product_feedback_chunks (document_id);
                CREATE INDEX IF NOT EXISTS idx_feedback_chunks_metadata 
                ON product_feedback_chunks USING gin (metadata);
            """))
            conn.commit()
    
    def add_documents(self, documents: List[Document]) -> List[str]:
        """Add documents to pgvector."""
        from sqlalchemy import text
        import uuid
        
        texts = [doc.page_content for doc in documents]
        embeddings = self.embeddings.embed_documents(texts)
        
        ids = []
        with self.engine.connect() as conn:
            for doc, embedding in zip(documents, embeddings):
                chunk_id = uuid.uuid4()
                doc_id = doc.metadata.get("document_id")
                chunk_index = doc.metadata.get("chunk_index", 0)
                
                conn.execute(text("""
                    INSERT INTO product_feedback_chunks 
                    (id, document_id, chunk_index, content, embedding, metadata)
                    VALUES (:id, :doc_id, :chunk_idx, :content, :embedding, :metadata)
                """), {
                    "id": chunk_id,
                    "doc_id": doc_id,
                    "chunk_idx": chunk_index,
                    "content": doc.page_content,
                    "embedding": embedding,
                    "metadata": doc.metadata,
                })
                ids.append(str(chunk_id))
            conn.commit()
        return ids
    
    def similarity_search(self, query: str, k: int, filter: Optional[Dict] = None) -> List[RetrievedChunk]:
        """Search for similar documents using cosine similarity."""
        from sqlalchemy import text
        
        query_embedding = self.embeddings.embed_query(query)
        
        # Build filter conditions
        where_clauses = []
        params = {"query_embedding": query_embedding, "k": k}
        
        if filter:
            for key, value in filter.items():
                if key == "source":
                    where_clauses.append("metadata->>'source' = :source")
                    params["source"] = value
                elif key == "product_area":
                    where_clauses.append("metadata->>'product_area' = :product_area")
                    params["product_area"] = value
                elif key == "sentiment":
                    where_clauses.append("metadata->>'sentiment' = :sentiment")
                    params["sentiment"] = value
        
        where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
        
        sql = f"""
            SELECT 
                content,
                metadata,
                1 - (embedding <=> :query_embedding) as similarity,
                document_id
            FROM product_feedback_chunks
            {where_sql}
            ORDER BY embedding <=> :query_embedding
            LIMIT :k
        """
        
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), params)
            chunks = []
            for row in result:
                chunks.append(RetrievedChunk(
                    content=row.content,
                    metadata=row.metadata,
                    score=float(row.similarity),
                    document_id=str(row.document_id),
                ))
            return chunks
    
    def similarity_search_with_score(self, query: str, k: int, filter: Optional[Dict] = None) -> List[tuple]:
        chunks = self.similarity_search(query, k, filter)
        return [(chunk.content, chunk.score, chunk.metadata) for chunk in chunks]
    
    def delete_documents(self, document_ids: List[str]) -> None:
        from sqlalchemy import text
        with self.engine.connect() as conn:
            conn.execute(text("""
                DELETE FROM product_feedback_chunks 
                WHERE document_id = ANY(:ids)
            """), {"ids": document_ids})
            conn.commit()


class HybridRetriever:
    """Hybrid retrieval combining vector search with keyword search."""
    
    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.top_k = settings.rag_top_k
        self.rerank = settings.rag_rerank
        
        if self.rerank:
            from sentence_transformers import CrossEncoder
            self.reranker = CrossEncoder(settings.rag_rerank_model)
        else:
            self.reranker = None
    
    def retrieve(self, query: str, filter: Optional[Dict] = None, k: Optional[int] = None) -> List[RetrievedChunk]:
        """Retrieve relevant chunks using hybrid search."""
        k = k or self.top_k
        
        # Vector search (get more for reranking)
        search_k = k * 3 if self.rerank else k
        vector_results = self.vector_store.similarity_search(query, search_k, filter)
        
        if not vector_results:
            return []
        
        # Rerank with cross-encoder if enabled
        if self.reranker and len(vector_results) > 1:
            pairs = [(query, chunk.content) for chunk in vector_results]
            scores = self.reranker.predict(pairs)
            
            # Combine vector score with rerank score
            for chunk, rerank_score in zip(vector_results, scores):
                chunk.score = 0.7 * chunk.score + 0.3 * float(rerank_score)
            
            # Sort by combined score
            vector_results.sort(key=lambda x: x.score, reverse=True)
        
        return vector_results[:k]
    
    def retrieve_with_citations(self, query: str, filter: Optional[Dict] = None, k: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve chunks with citation information."""
        chunks = self.retrieve(query, filter, k)
        
        results = []
        for i, chunk in enumerate(chunks):
            results.append({
                "citation_id": i + 1,
                "content": chunk.content,
                "metadata": chunk.metadata,
                "score": chunk.score,
                "document_id": chunk.document_id,
            })
        return results


class FeedbackIngestionPipeline:
    """Pipeline for ingesting feedback into vector store."""
    
    def __init__(self, vector_store: VectorStore = None):
        self.processor = DocumentProcessor()
        self.vector_store = vector_store or self._create_vector_store()
    
    def _create_vector_store(self) -> VectorStore:
        if settings.vector_db_type == "qdrant":
            return QdrantVectorStore()
        else:
            return PgVectorStore()
    
    def ingest_feedback(self, feedback_list: List[ProductFeedback]) -> Dict[str, int]:
        """Ingest a list of feedback records."""
        all_chunks = []
        
        for feedback in feedback_list:
            chunks = self.processor.process_feedback(feedback)
            for i, chunk in enumerate(chunks):
                chunk.metadata["chunk_index"] = i
                chunk.metadata["chunk_count"] = len(chunks)
            all_chunks.extend(chunks)
        
        if all_chunks:
            self.vector_store.add_documents(all_chunks)
        
        return {"feedback_count": len(feedback_list), "chunks_created": len(all_chunks)}
    
    def ingest_support_tickets(self, tickets: List[SupportTicket]) -> Dict[str, int]:
        """Ingest a list of support tickets."""
        all_chunks = []
        
        for ticket in tickets:
            chunks = self.processor.process_support_ticket(ticket)
            for i, chunk in enumerate(chunks):
                chunk.metadata["chunk_index"] = i
                chunk.metadata["chunk_count"] = len(chunks)
            all_chunks.extend(chunks)
        
        if all_chunks:
            self.vector_store.add_documents(all_chunks)
        
        return {"ticket_count": len(tickets), "chunks_created": len(all_chunks)}
    
    def reingest_all(self, session) -> Dict[str, int]:
        """Re-ingest all feedback and tickets from database."""
        feedback = session.query(ProductFeedback).all()
        tickets = session.query(SupportTicket).all()
        
        fb_result = self.ingest_feedback(feedback)
        tk_result = self.ingest_support_tickets(tickets)
        
        return {**fb_result, **tk_result}


def get_vector_store() -> VectorStore:
    """Get the configured vector store."""
    if settings.vector_db_type == "qdrant":
        return QdrantVectorStore()
    return PgVectorStore()


def get_retriever() -> HybridRetriever:
    """Get the hybrid retriever."""
    return HybridRetriever(get_vector_store())


def get_ingestion_pipeline() -> FeedbackIngestionPipeline:
    """Get the ingestion pipeline."""
    return FeedbackIngestionPipeline()