import asyncio
import logging
from app.services.ingestion import ingest_documents

logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    asyncio.run(ingest_documents())