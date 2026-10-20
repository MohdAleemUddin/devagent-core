import asyncio
from app.services.rag import query_rag

async def main():
    question = "How are tool inputs validated in DevAgent Core?"
    answer = await query_rag(question)
    
    print(f"\n💡 Final AI Answer:\n{answer}\n" + "="*50)

if __name__ == "__main__":
    asyncio.run(main())