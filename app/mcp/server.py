import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, TextContent

# Initialize the MCP server instance
app = Server("devagent-core-mcp")

# Define the local docs path
DOCS_DIR = project_root / "docs"

# 1. Register handlers for listing and reading resources
@app.list_resources()
async def list_resources() -> list[Resource]:
    resources = []
    if DOCS_DIR.exists():
        for file_path in DOCS_DIR.glob("*.md"):
            resources.append(
                Resource(
                    uri=f"file:///{str(file_path).replace(os.sep, '/')}",
                    name=file_path.name,
                    description=f"Project documentation file: {file_path.name}",
                    mimeType="text/markdown"
                )
            )
    return resources

@app.read_resource()
async def read_resource(uri: str) -> str:
    parsed_uri = urlparse(str(uri))
    if parsed_uri.scheme != "file" or parsed_uri.netloc not in ("", "localhost"):
        raise ValueError(f"Resource not found: {uri}")

    path_str = unquote(parsed_uri.path)
    if os.name == "nt" and len(path_str) >= 3 and path_str[0] == "/" and path_str[2] == ":":
        path_str = path_str[1:]
    file_path = Path(path_str).resolve()
    docs_root = DOCS_DIR.resolve()
    if (
        not file_path.is_relative_to(docs_root)
        or file_path.suffix.lower() != ".md"
        or not file_path.is_file()
    ):
        raise ValueError(f"Resource not found: {uri}")
    return file_path.read_text(encoding="utf-8")

# 2. Register tools for RAG querying
@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_devagent_docs",
            description="Query the DevAgent Core vector database using semantic search and local LLM generation.",
            inputSchema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The technical question regarding architecture, database, or security."
                    }
                },
                "required": ["question"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name != "search_devagent_docs":
        raise ValueError(f"Unknown tool: {name}")
    
    question = arguments.get("question")
    try:
        from app.services.rag import query_rag
        answer = await query_rag(question)
        return [TextContent(type="text", text=answer)]
    except Exception as e:
        return [TextContent(type="text", text=f"Error executing vector search: {str(e)}")]

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())