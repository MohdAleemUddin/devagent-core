import asyncio
from app.agent.executor import run_react_agent

async def main():
    # Directly await the agent function (no nested asyncio.run!)
    result = await run_react_agent("Check the status of git in the project root using a tool.")
    print(f"\n✨ Final Result:\n{result}")

if __name__ == "__main__":
    asyncio.run(main())