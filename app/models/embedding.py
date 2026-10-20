from sqlalchemy import Column, Integer, Text, String, DateTime
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from app.core.database import Base

class DocumentEmbedding(Base):
    """
    SQLAlchemy model for storing chunked documentation text and their 
    768-dimensional vector embeddings using pgvector.
    """
    __tablename__ = "document_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(255), nullable=False, index=True)  # e.g., "docs/architecture.md"
    content = Column(Text, nullable=False)                     # The actual chunk text
    embedding = Column(Vector(768), nullable=False)            # 768-dim vector for nomic-embed-text
    created_at = Column(DateTime(timezone=True), server_default=func.now())