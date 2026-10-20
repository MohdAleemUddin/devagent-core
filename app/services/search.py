import httpx
from sqlalchemy import text
from app.core.database import SessionLocal
from app.core.config import settings

async def get_embedding_from_ollama(text_content: str) -> list[float]:
    """Helper to convert a search query into a 768-dim vector using Ollama."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/embeddings",
            json={
                "model": "nomic-embed-text:latest",
                "prompt": text_content
            },
            timeout=30.0
        )
        if response.status_code != 200:
            raise RuntimeError(f"Ollama query embedding failed: {response.text}")
        
        data = response.json()
        return data.get("embedding")


async def search_documents(query: str, top_k: int = 2):
    """
    Takes a search query, vectorizes it, and performs a vector similarity search 
    against PostgreSQL document embeddings.
    """
    print(f"\nSearching vector database for: '{query}'")
    
    # 1. Convert user query to vector
    query_vector = await get_embedding_from_ollama(query)

    # 2. Query PostgreSQL using pgvector distance operator (<=>)
    # Lower distance = higher similarity
    async with SessionLocal() as session:
        sql = text("""
            SELECT source, content, (embedding <=> CAST(:query_vector AS vector)) as distance
            FROM document_embeddings
            ORDER BY distance ASC
            LIMIT :top_k;
        """)
        
        result = await session.execute(
            sql, 
            {"query_vector": str(query_vector), "top_k": top_k}
        )
        rows = result.fetchall()

        print(f"\nTop {top_k} results found:")
        for row in rows:
            print(f"--------------------------------------------------")
            print(f"Source: {row.source}")
            print(f"Distance Score: {row.distance:.4f} (lower is closer)")
            print(f"Content: {row.content}")
        print(f"--------------------------------------------------\n")