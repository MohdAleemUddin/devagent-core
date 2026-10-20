# import asyncio
# from app.mcp.server import app as mcp_app, list_resources, read_resource, list_tools, call_tool

# async def test_server_internals():
#     print("🧪 Testing MCP Server Handlers Directly...\n")

#     # 1. Test listing resources
#     print("📚 Testing list_resources()...")
#     resources = await list_resources()
#     for res in resources:
#         print(f"  • Found: {res.name} ({res.uri})")
#     print()

#     # 2. Test reading a resource if available
#     if resources:
#         first_res = resources[0]
#         print(f"📖 Testing read_resource() for: {first_res.name}...")
#         content = await read_resource(first_res.uri)
#         print(f"  • Preview (first 150 chars): {content[:150]}...\n")

#     # 3. Test listing tools
#     print("🛠️ Testing list_tools()...")
#     tools = await list_tools()
#     for tool in tools:
#         print(f"  • Tool: {tool.name} - {tool.description}")
#     print()

#     # 4. Test calling the RAG search tool directly
#     print("🚀 Testing call_tool('search_devagent_docs')...")
#     result = await call_tool("search_devagent_docs", {"question": "What architecture does DevAgent Core use?"})
#     for content in result:
#         print(f"\n📬 Tool Response:\n{content.text}\n")

# if __name__ == "__main__":
#     asyncio.run(test_server_internals())

import asyncio
from app.mcp.server import list_resources, read_resource, list_tools, call_tool

async def test_server_internals():
    print("🧪 Testing MCP Server Handlers Directly...\n")

    # 1. Test listing resources
    print("📚 Testing list_resources()...")
    resources = await list_resources()
    for res in resources:
        print(f"  • Found: {res.name} ({res.uri})")
    print()

    # 2. Test reading a resource
    if resources:
        first_res = resources[0]
        print(f"📖 Testing read_resource() for: {first_res.name}...")
        content = await read_resource(first_res.uri)
        print(f"  • Preview (first 150 chars): {content[:150]}...\n")

    # 3. Test listing tools
    print("🛠️ Testing list_tools()...")
    tools = await list_tools()
    for tool in tools:
        print(f"  • Tool: {tool.name} - {tool.description}")
    print()

    # 4. Test calling the tool handler directly
    print("🚀 Testing call_tool() for 'search_devagent_docs'...")
    result = await call_tool(
        name="search_devagent_docs", 
        arguments={"question": "What architecture does DevAgent Core use?"}
    )
    
    print("\n📬 Tool Response:")
    for content in result:
        print(content.text)

if __name__ == "__main__":
    asyncio.run(test_server_internals())