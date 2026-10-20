import asyncio
from app.services.search import search_documents

async def main():
    # Test queries targeting our ingested sample docs
    await search_documents("How does validation work for tool inputs?")
    await search_documents("What database extension is used to store vectors?")

if __name__ == "__main__":
    asyncio.run(main())