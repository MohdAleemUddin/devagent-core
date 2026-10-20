import inspect
import logging
from typing import Callable, Dict, Any, get_type_hints
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class Tool:
    def __init__(self, name: str, description: str, func: Callable, args_schema: type[BaseModel]):
        self.name = name
        self.description = description
        self.func = func
        self.args_schema = args_schema

    def to_openai_schema(self) -> Dict[str, Any]:
        """Convert the Pydantic schema into OpenAI/Ollama-compatible tool definition format"""
        schema = self.args_schema.model_json_schema()
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", []),
                },
            },
        }

    async def execute(self, **kwargs) -> Any:
        """Asynchronously execute the underlying tool function with validated arguments"""
        if inspect.iscoroutinefunction(self.func):
            return await self.func(**kwargs)
        else:
            return self.func(**kwargs)


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, name: str, description: str, args_schema: type[BaseModel]):
        """Decorator to register a python function as an agent tool"""
        def decorator(func: Callable):
            if name in self._tools:
                logger.warning(f"Tool {name} is already registered. Overwriting...")
            self._tools[name] = Tool(
                name=name,
                description=description,
                func=func,
                args_schema=args_schema
            )
            return func
        return decorator

    def get_tool(self, name: str) -> Tool:
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' is not registered in the ToolRegistry.")
        return self._tools[name]

    def get_all_schemas(self) -> list[Dict[str, Any]]:
        """Return schemas for all registered tools so the LLM can see them"""
        return [tool.to_openai_schema() for tool in self._tools.values()]


# Global shared instance of the tool registry
tool_registry = ToolRegistry()