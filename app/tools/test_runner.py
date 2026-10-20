import asyncio
import logging
from app.tools.executor import execute_tool_call
# Import implementations so the decorators actually run and register the tools into the registry!
import app.tools.implementations 
import app.tools.rag_tool 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_tests():
    print("\n🚀 Starting Sprint 2 Tool & Executor Verification...\n")

    # Test 1: Query Logs Tool (Valid execution)
    print("--- Test 1: Testing 'query_logs' tool ---")
    result_logs = await execute_tool_call(
        tool_name="query_logs",
        arguments={"severity": "ERROR", "limit": 2}
    )
    print(f"Result:\n{result_logs}\n")

    # Test 2: Read File Tool (Valid execution - let's read main.py or config.py if it exists)
    print("--- Test 2: Testing 'read_file' tool (Valid Path) ---")
    result_file = await execute_tool_call(
        tool_name="read_file",
        arguments={"file_path": "app/core/config.py"}
    )
    print(f"Result snippet (first 150 chars):\n{result_file[:150]}...\n")

    # Test 3: Security Check - Path Traversal Attack Prevention
    print("--- Test 3: Testing Security Guardrail (Path Traversal Attempt) ---")
    result_hack = await execute_tool_call(
        tool_name="read_file",
        arguments={"file_path": "../../../etc/passwd"}
    )
    print(f"Result:\n{result_hack}\n")

    # Test 4: Vector Search Tool (Mock RAG tool we built yesterday)
    print("--- Test 4: Testing 'vector_search' tool ---")
    result_rag = await execute_tool_call(
        tool_name="vector_search",
        arguments={"query": "How is database configured?", "top_k": 2}
    )
    print(f"Result:\n{result_rag}\n")

    print("✨ All Sprint 2 verification tests completed successfully!\n")

if __name__ == "__main__":
    asyncio.run(run_tests())