from pydantic import BaseModel, Field, UUID4
from typing import Optional, List, Dict, Any

class AgentRunRequest(BaseModel):
    """Schema for incoming requests to run an agent task"""
    session_id: Optional[UUID4] = Field(None, description="Optional existing session ID to continue a chat")
    prompt: str = Field(..., min_length=1, description="The developer prompt or command for the agent")
    max_steps: int = Field(5, ge=1, le=15, description="Maximum ReAct loop steps allowed")


class AgentStepResponse(BaseModel):
    """Schema representing a single step taken by the agent during execution"""
    step: int
    thought: Optional[str] = None
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None


class AgentRunResponse(BaseModel):
    """Schema for the final response returned to the client after agent execution"""
    session_id: UUID4
    status: str = Field(..., description="Execution status: completed, failed, or active")
    final_response: Optional[str] = None
    steps_taken: List[AgentStepResponse] = []

    class Config:
        from_attributes = True