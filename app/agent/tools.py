# import os
# import subprocess
# from pathlib import Path
# from pydantic import BaseModel, Field

# PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# class ReadFileSchema(BaseModel.的表现 if False else BaseModel):  # standard BaseModel
#     pass

# class ReadFileArgs(BaseModel):
#     file_path: str = Field(..., description="Relative path to the file to read within the project root.")

# def tool_read_file(file_path: str) -> str:
#     """Read the contents of a file in the project."""
#     try:
#         target_path = (PROJECT_ROOT / file_path).resolve()
#         # Security check against path traversal
#         if not target_path.is_relative_to(PROJECT_ROOT):
#             return "Error: Access denied. Path is outside the project root."
#         if not target_path.exists():
#             return f"Error: File '{file_path}' does not exist."
#         return target_path.read_text(encoding="utf-8")
#     except Exception as e:
#         return f"Error reading file: {str(e)}"


# class WriteFileArgs(BaseModel):
#     file_path: str = Field(..., description="Relative path to the file to write.")
#     content: str = Field(..., description="The full text content to write to the file.")

# def tool_write_file(file_path: str, content: str) -> str:
#     """Create or overwrite a file in the project."""
#     try:
#         target_path = (PROJECT_ROOT / file_path).resolve()
#         if not target_path.is_relative_to(PROJECT_ROOT):
#             return "Error: Access denied. Path is outside the project root."
#         target_path.parent.mkdir(parents=True, exist_ok=True)
#         target_path.write_text(content, encoding="utf-8")
#         return f"Successfully wrote to {file_path}"
#     except Exception as e:
#         return f"Error writing file: {str(e)}"


# class RunCommandArgs(BaseModel):
#     command: str = Field(..., description="Shell command to execute (e.g. pytest, git status).")

# def tool_run_command(command: str) -> str:
#     """Execute a safe local shell command."""
#     # Restrict dangerous commands
#     forbidden = ["rm -rf /", "mkfs", ":(){:|:&};:"]
#     if any(f in command for f in forbidden):
#         return "Error: Command blocked for security reasons."
#     try:
#         result = subprocess.run(
#             command, 
#             shell=True, 
#             cwd=str(PROJECT_ROOT), 
#             capture_output=True, 
#             text=True, 
#             timeout=30
#         )
#         output = result.stdout + "\n" + result.stderr
#         return output.strip() if output.strip() else "Command executed successfully with no output."
#     except Exception as e:
#         return f"Error executing command: {str(e)}"

# # Tool registry mapping names to functions and metadata
# AVAILABLE_TOOLS = {
#     "read_file": {
#         "function": tool_read_file,
#         "description": "Read the contents of a project file.",
#         "args_schema": ReadFileArgs
#     },
#     "write_file": {
#         "function": tool_write_file,
#         "description": "Create or modify a file in the project.",
#         "args_schema": WriteFileArgs
#     },
#     "run_command": {
#         "function": tool_run_command,
#         "description": "Run a local terminal command (e.g., tests, linter).",
#         "args_schema": RunCommandArgs
#     }
# }


import subprocess
from pathlib import Path
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

class ReadFileArgs(BaseModel):
    file_path: str = Field(..., description="Relative path to the file to read within the project root.")

def tool_read_file(file_path: str) -> str:
    """Read the contents of a file in the project."""
    try:
        target_path = (PROJECT_ROOT / file_path).resolve()
        # Security check against path traversal
        if not target_path.is_relative_to(PROJECT_ROOT):
            return "Error: Access denied. Path is outside the project root."
        if not target_path.exists():
            return f"Error: File '{file_path}' does not exist."
        return target_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"Error reading file: {str(e)}"


class WriteFileArgs(BaseModel):
    file_path: str = Field(..., description="Relative path to the file to write.")
    content: str = Field(..., description="The full text content to write to the file.")

def tool_write_file(file_path: str, content: str) -> str:
    """Create or overwrite a file in the project."""
    try:
        target_path = (PROJECT_ROOT / file_path).resolve()
        if not target_path.is_relative_to(PROJECT_ROOT):
            return "Error: Access denied. Path is outside the project root."
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


class RunCommandArgs(BaseModel):
    command: str = Field(..., description="Read-only Git status command.")

def tool_run_command(command: str) -> str:
    """Run only the supported read-only Git status commands without a shell."""
    allowed_commands = {
        "git status": ["git", "status"],
        "git status --short": ["git", "status", "--short"],
    }
    argv = allowed_commands.get(command.strip())
    if argv is None:
        return "Error: Command is not allowed. Supported commands: git status, git status --short."

    try:
        result = subprocess.run(
            argv,
            shell=False,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = result.stdout + "\n" + result.stderr
        return output.strip() if output.strip() else "Command executed successfully with no output."
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 10 seconds."
    except Exception as e:
        return f"Error executing command: {str(e)}"

# Tool registry mapping names to functions and metadata
AVAILABLE_TOOLS = {
    "read_file": {
        "function": tool_read_file,
        "description": "Read the contents of a project file.",
        "args_schema": ReadFileArgs
    },
    "write_file": {
        "function": tool_write_file,
        "description": "Create or modify a file in the project.",
        "args_schema": WriteFileArgs
    },
    "run_command": {
        "function": tool_run_command,
        "description": "Read the Git status in the project root.",
        "args_schema": RunCommandArgs
    }
}