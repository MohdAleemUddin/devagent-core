import json
import logging
from typing import Dict, Any
from app.tools.registry import tool_registry

logger = logging.getLogger(__name__)

async def execute_tool_call(tool_name: str, arguments: Dict[str, Any]) -> str:
    """
    Safely executes a registered tool given its name and raw argument dictionary.
    Handles Pydantic validation, execution errors, and ensures safe fallbacks.
    """
    try:
        # 1. Fetch the tool from our global registry
        try:
            tool = tool_registry.get_tool(tool_name)
        except ValueError as e:
            logger.error(f"Tool dispatch error: {str(e)}")
            return f"Error: Tool '{tool_name}' does not exist. Please check available tools."

        # 2. Validate and parse arguments using the tool's Pydantic schema
        try:
            validated_args = tool.args_schema(**arguments)
        except Exception as validation_error:
            logger.error(f"Validation failed for tool '{tool_name}': {str(validation_error)}")
            return f"Error: Invalid arguments provided for tool '{tool_name}': {str(validation_error)}"

        # 3. Execute the tool asynchronously using validated dictionary fields
        logger.info(f"Executing tool '{tool_name}' with args: {arguments}")
        result = await tool.execute(**validated_args.model_dump())
        
        return str(result)

    except Exception as e:
        logger.error(f"Unexpected error during execution of tool '{tool_name}': {str(e)}")
        return f"Error executing tool '{tool_name}': {str(e)}"