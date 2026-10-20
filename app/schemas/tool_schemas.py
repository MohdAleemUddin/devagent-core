from pydantic import BaseModel, Field
from typing import Optional

class QueryLogsToolSchema(BaseModel):
    """Schema for arguments required by the database log search tool"""
    severity: str = Field(
        ..., 
        description="Log severity level to filter by. Must be one of: INFO, WARNING, ERROR, CRITICAL"
    )
    limit: Optional[int] = Field(
        5, 
        ge=1, 
        le=20, 
        description="Maximum number of log records to return"
    )


class VectorSearchToolSchema(BaseModel):
    """Schema for arguments required by the RAG vector search tool"""
    query: str = Field(
        ..., 
        description="The semantic search query string to find relevant documentation or code snippets"
    )
    top_k: Optional[int] = Field(
        3, 
        ge=1, 
        le=10, 
        description="Number of top similar documentation chunks to retrieve"
    )


class ReadFileToolSchema(BaseModel):
    """Schema for arguments required by the local file reader tool"""
    file_path: str = Field(
        ..., 
        description="The relative file path of the code or configuration file to read"
    )