import os
import logging
from pathlib import Path
from app.tools.registry import tool_registry
from app.schemas.tool_schemas import ReadFileToolSchema, QueryLogsToolSchema

logger = logging.getLogger(__name__)

# Define the root directory safely (relative to project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@tool_registry.register(
    name="read_file",
    description="Reads the text content of a code or configuration file from the project workspace.",
    args_schema=ReadFileToolSchema
)
async def read_file_tool(file_path: str) -> str:
    """
    Safely reads a local file given its relative path.
    Prevents path traversal attacks by ensuring the file stays inside the project root.
    """
    try:
        # Resolve path safely
        target_path = (PROJECT_ROOT / file_path).resolve()
        
        # Security check: ensure target path is actually inside the project root
        if not target_path.is_relative_to(PROJECT_ROOT):
            return "Error: Access denied. Path traversal outside project root is forbidden."

        if not target_path.exists():
            return f"Error: File '{file_path}' does not exist."

        if not target_path.is_file():
            return f"Error: Path '{file_path}' is a directory, not a file."

        # Read file content safely
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        logger.info(f"Successfully read file: {file_path}")
        return content

    except Exception as e:
        logger.error(f"Failed to read file {file_path}: {str(e)}")
        return f"Error reading file: {str(e)}"


@tool_registry.register(
    name="query_logs",
    description="Queries application or system logs filtered by severity level (INFO, WARNING, ERROR, CRITICAL).",
    args_schema=QueryLogsToolSchema
)
async def query_logs_tool(severity: str, limit: int = 5) -> str:
    """
    Simulates fetching system logs from a database or log file based on severity.
    """
    # Normalize severity input
    severity = severity.upper()
    valid_severities = ["INFO", "WARNING", "ERROR", "CRITICAL"]
    
    if severity not in valid_severities:
        return f"Error: Invalid severity '{severity}'. Must be one of: {', '.join(valid_severities)}"

    # Simulated log database records for demonstration
    mock_logs = [
        {"timestamp": "2026-10-19 10:00:12", "level": "INFO", "message": "Database connection pool initialized successfully."},
        {"timestamp": "2026-10-19 10:05:30", "level": "WARNING", "message": "High memory consumption detected on worker thread 2."},
        {"timestamp": "2026-10-19 10:12:04", "level": "ERROR", "message": "Failed to connect to external vector embedding endpoint."},
        {"timestamp": "2026-10-19 10:15:45", "level": "INFO", "message": "Agent session #42 successfully created."},
        {"timestamp": "2026-10-19 10:20:01", "level": "CRITICAL", "message": "Database deadlock encountered during transaction commit."},
        {"timestamp": "2026-10-19 10:22:15", "level": "ERROR", "message": "Tool execution timeout exceeded for 'query_logs'."},
    ]

    # Filter logs by requested severity
    filtered_logs = [log for log in mock_logs if log["level"] == severity]

    if not filtered_logs:
        return f"No logs found with severity level: {severity}"

    # Apply limit
    limited_logs = filtered_logs[:limit]
    
    # Format output as a clean string for the agent
    result_str = f"Found {len(limited_logs)} log(s) for severity {severity}:\n"
    for log in limited_logs:
        result_str += f"[{log['timestamp']}] [{log['level']}] {log['message']}\n"

    return result_str.strip()