import asyncio
import os
import sys
from pathlib import Path
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

async def run_mcp_test():
    print("🔌 Starting MCP Server subprocess...")

    # Determine absolute path to app/mcp/server.py and project root
    project_root = Path(__file__).resolve().parent
    server_script = project_root / "app" / "mcp" / "server.py"

    # Set up environment variables so the subprocess can import project modules
    env = dict(os.environ)
    env["PYTHONPATH"] = str(project_root)

    # Configure the command to run your MCP server script
    server_params = StdioServerParameters(
        command=sys.executable,  # Uses your virtual environment Python
        args=[str(server_script)],
        env=env
    )

    # Establish stdio client connection to your MCP server
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # 1. Initialize protocol handshake
            await session.initialize()
            print("✅ MCP Handshake Successful!\n")

            # 2. List exposed Resources
            print("📚 Listing Available MCP Resources:")
            resources_result = await session.list_resources()
            for resource in resources_result.resources:
                print(f"  • [{resource.name}] -> {resource.uri}")
            print()

            # 3. List exposed Tools
            print("🛠️ Listing Available MCP Tools:")
            tools_result = await session.list_tools()
            for tool in tools_result.tools:
                print(f"  • Tool Name: {tool.name}")
                print(f"    Description: {tool.description}")
            print()

            # 4. Call the RAG search tool through MCP
            test_question = "What architecture does DevAgent Core use?"
            print(f"🚀 Executing MCP Tool 'search_devagent_docs' with question: '{test_question}'...")
            
            tool_call_result = await session.call_tool(
                "search_devagent_docs",
                arguments={"question": test_question}
            )

            print("\n📬 Response received from MCP Server:")
            for content in tool_call_result.content:
                if content.type == "text":
                    print(f"\n{content.text}\n")

if __name__ == "__main__":
    asyncio.run(run_mcp_test())