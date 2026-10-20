import httpx
import json
import re
from app.core.config import settings
from app.agent.tools import AVAILABLE_TOOLS

SYSTEM_PROMPT = """You are DevAgent Core, an expert autonomous AI software engineering assistant.
You solve tasks step-by-step using a ReAct (Reasoning and Acting) loop.

You have access to the following tools:
- read_file(file_path: str): Read a project file.
- write_file(file_path: str, content: str): Create or overwrite a project file.
- run_command(command: str): Read the Git status in the project root.

To use a tool, you MUST output your response in this exact format:
THOUGHT: [Your reasoning about what to do next]
TOOL: tool_name(arg1="value1", arg2="value2")

If you have finished the task or do not need a tool, output:
THOUGHT: [Your final reasoning]
FINAL_ANSWER: [Your final response to the user]
"""

def parse_tool_args(args_str: str) -> dict:
    """
    Safely parses tool arguments formatted like: key1="val1", key2="val2"
    into a standard python keyword arguments dictionary using regex.
    """
    kwargs = {}
    pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s,]+))'
    matches = re.findall(pattern, args_str)
    for key, double_val, single_val, raw_val in matches:
        val = double_val if double_val != '' else (single_val if single_val != '' else raw_val)
        kwargs[key] = val
    return kwargs

async def run_react_agent(user_goal: str, max_turns: int = 5) -> str:
    """
    Executes the multi-step ReAct loop with Ollama.
    """
    print(f"\nStarting autonomous agent goal: '{user_goal}'")
    
    conversation_history = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Task: {user_goal}"}
    ]

    async with httpx.AsyncClient(timeout=120.0) as client:
        for turn in range(max_turns):
            print(f"\n--- Turn {turn + 1}/{max_turns} ---")
            
            # Call Ollama
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": "llama3.2:3b",
                    "messages": conversation_history,
                    "stream": False
                },
                timeout=60.0
            )
            
            if response.status_code != 200:
                return f"Agent failed to communicate with Ollama: {response.text}"
                
            assistant_message = response.json().get("message", {}).get("content", "")
            print(f"Agent output:\n{assistant_message}")
            
            conversation_history.append({"role": "assistant", "content": assistant_message})

            # Check for FINAL_ANSWER
            if "FINAL_ANSWER:" in assistant_message:
                match = re.search(r"FINAL_ANSWER:\s*(.*)", assistant_message, re.DOTALL)
                return match.group(1).strip() if match else assistant_message

            # Check for TOOL call
            tool_match = re.search(r"TOOL:\s*([a-zA-Z_][a-zA-Z0-9_]*)\((.*)\)", assistant_message, re.DOTALL)
            if tool_match:
                tool_name = tool_match.group(1)
                args_str = tool_match.group(2)
                
                if tool_name not in AVAILABLE_TOOLS:
                    observation = f"Error: Tool '{tool_name}' does not exist."
                else:
                    try:
                        kwargs = parse_tool_args(args_str)
                        tool_func = AVAILABLE_TOOLS[tool_name]["function"]
                        print(f"Executing tool: {tool_name} with args {kwargs}")
                        observation = tool_func(**kwargs)
                    except Exception as e:
                        observation = f"Error executing tool: {str(e)}"
                
                print(f"Observation:\n{observation}")
                conversation_history.append({
                    "role": "user", 
                    "content": f"OBSERVATION: {observation}"
                })
            else:
                conversation_history.append({
                    "role": "user",
                    "content": "REMINDER: You must output either 'TOOL: name(args)' or 'FINAL_ANSWER: response'."
                })

        return "Agent reached maximum execution turns without completing the task."