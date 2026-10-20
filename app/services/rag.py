# import httpx
# from app.services.search import search_documents
# from app.core.config import settings
# from app.core.database import SessionLocal
# from sqlalchemy import text

# async def query_rag(user_question: str) -> str:
#     """
#     Complete RAG Pipeline:
#     1. Retrieve relevant doc chunks from PostgreSQL via vector similarity.
#     2. Build a grounded prompt containing the context.
#     3. Send it to Ollama to generate a precise answer.
#     """
#     print(f"\n🤖 Running full RAG pipeline for: '{user_question}'")
    
#     # 1. Retrieve top 2 matching document chunks using our embedding search
#     query_vector = await search_documents.__globals__['get_embedding_from_ollama'](user_question)
    
#     async with SessionLocal() as session:
#         sql = text("""
#             SELECT source, content, (embedding <=> CAST(:query_vector AS vector)) as distance
#             FROM document_embeddings
#             ORDER BY distance ASC
#             LIMIT 2;
#         """)
#         result = await session.execute(sql, {"query_vector": str(query_vector)})
#         rows = result.fetchall()

#     # 2. Extract and format the context
#     context_blocks = []
#     for row in rows:
#         context_blocks.append(f"Source: {row.source}\nContent: {row.content}")
    
#     context_str = "\n\n".join(context_blocks)

#     # 3. Construct the prompt for the LLM
#     prompt = f"""You are DevAgent Core, an expert AI software engineering assistant. 
# Answer the user's question accurately using ONLY the provided context below. If you don't know the answer based on the context, say you don't know.

# Context:
# {context_str}

# User Question: {user_question}
# Answer:"""

#     print("🧠 Sending context and prompt to Ollama LLM...")

#     # 4. Call Ollama generation API (using llama3 or your default chat model)
#     async with httpx.AsyncClient(timeout=120.0) as client:
#         response = await client.post(
#             f"{settings.OLLAMA_BASE_URL}/api/generate",
#             json={
#                 "model": "llama3.2:3b",  # You can change this to whatever chat model you have in Ollama
#                 "prompt": prompt,
#                 "stream": False
#             },
#             timeout=60.0
#         )
        
#         if response.status_code != 200:
#             # Fallback message if llama3 isn't pulled yet
#             return f"Retrieved Context successfully, but LLM generation failed: {response.text}"
        
#         data = response.json()
#         return data.get("response", "No response generated.")

import httpx
from pathlib import Path
from app.services.search import get_embedding_from_ollama, search_documents
from app.core.config import settings
from app.core.database import SessionLocal
from sqlalchemy import text

async def query_rag(user_question: str) -> str:
    """
    Complete RAG Pipeline:
    1. Retrieve relevant doc chunks from PostgreSQL via vector similarity.
    2. Build a grounded prompt containing the context.
    3. Send it to Ollama to generate a precise answer.
    """
    print(f"\nRunning full RAG pipeline for: '{user_question}'")
    
    # 1. Retrieve top 2 matching document chunks using our embedding search
    query_vector = await get_embedding_from_ollama(user_question)
    
    async with SessionLocal() as session:
        sql = text("""
            SELECT source, content, (embedding <=> CAST(:query_vector AS vector)) as distance
            FROM document_embeddings
            ORDER BY distance ASC
            LIMIT 2;
        """)
        result = await session.execute(sql, {"query_vector": str(query_vector)})
        rows = result.fetchall()

    # 2. Extract and format the context
    context_blocks = []
    for row in rows:
        context_blocks.append(f"Source: {row.source}\nContent: {row.content}")
    
    context_str = "\n\n".join(context_blocks)

    # 3. Construct the prompt for the LLM
    prompt = f"""You are DevAgent Core, an expert AI software engineering assistant. 
Answer the user's question accurately using ONLY the provided context below. If you don't know the answer based on the context, say you don't know.

Context:
{context_str}

User Question: {user_question}
Answer:"""

    print("Sending context and prompt to Ollama LLM...")

    # 4. Call Ollama generation API
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json={
                "model": "llama3.2:3b",
                "prompt": prompt,
                "stream": False
            },
            timeout=60.0
        )
        
        if response.status_code != 200:
            return f"Retrieved Context successfully, but LLM generation failed: {response.text}"
        
        data = response.json()
        return data.get("response", "No response generated.")


async def ingest_document_file(file_path: Path):
    """
    Reads a markdown document, chunks its content, generates embeddings via Ollama,
    and stores/updates them in the PostgreSQL document_embeddings table.
    """
    print(f"\nIngesting document: {file_path.name}")
    
    if not file_path.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    content = file_path.read_text(encoding="utf-8")
    source_name = file_path.name

    # Simple paragraph/section chunking
    raw_chunks = [chunk.strip() for chunk in content.split("\n\n") if chunk.strip()]

    # Generate embeddings before replacing existing rows so a failed request
    # leaves the previously indexed document intact.
    embeddings = [
        await get_embedding_from_ollama(chunk)
        for chunk in raw_chunks
    ]

    async with SessionLocal() as session:
        async with session.begin():
            await session.execute(
                text("DELETE FROM document_embeddings WHERE source = :source"),
                {"source": source_name},
            )

            for chunk, embedding in zip(raw_chunks, embeddings):
                insert_sql = text("""
                    INSERT INTO document_embeddings (source, content, embedding)
                    VALUES (:source, :content, CAST(:embedding AS vector))
                """)
                await session.execute(
                    insert_sql,
                    {
                        "source": source_name,
                        "content": chunk,
                        "embedding": str(embedding),
                    },
                )
    print(f"Successfully embedded and stored {len(raw_chunks)} chunks for {source_name}!")