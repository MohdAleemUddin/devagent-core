# from fastapi import FastAPI, HTTPException, status
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel, Field

# from app.core.config import settings
# from app.services.rag import query_rag

# # Initialize FastAPI application with settings from our config
# app = FastAPI(
#     title=settings.PROJECT_NAME,
#     version="1.0.0",
#     docs_url=f"{settings.API_V1_STR}/docs",
#     redoc_url=f"{settings.API_V1_STR}/redoc",
# )

# # Configure CORS middleware (allows frontend/external clients to talk to your API safely)
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],  # In production, restrict this to your frontend domain
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Pydantic schemas for the RAG query endpoint
# class QueryRequest(BaseModel):
#     question: str = Field(..., description="The technical question to ask DevAgent Core", example="How are tool inputs validated?")

# class QueryResponse(BaseModel):
#     question: str
#     answer: str

# @app.get(f"{settings.API_V1_STR}/health", tags=["System Health"])
# async def health_check():
#     """
#     Health check endpoint to verify the server is running and configured correctly.
#     """
#     return {
#         "status": "healthy",
#         "project": settings.PROJECT_NAME,
#         "model_in_use": settings.MODEL_NAME,
#         "environment": "debug" if settings.DEBUG else "production"
#     }

# @app.post(f"{settings.API_V1_STR}/query", response_model=QueryResponse, tags=["RAG Engine"])
# async def ask_devagent(payload: QueryRequest):
#     """
#     Accepts a technical question, runs the complete RAG pipeline 
#     (Vector Search + LLM Generation), and returns the grounded answer.
#     """
#     if not payload.question.strip():
#         raise HTTPException(status_code=400, detail="Question cannot be empty.")
    
#     try:
#         answer = await query_rag(payload.question)
#         return QueryResponse(question=payload.question, answer=answer)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"RAG execution failed: {str(e)}")

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)

import logging
from ipaddress import ip_address

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator

from app.agent.executor import run_react_agent
from app.services.rag import query_rag

app = FastAPI(title="DevAgent Core", version="1.0.0")
logger = logging.getLogger(__name__)

# Request schemas
class AgentRequest(BaseModel):
    goal: str = Field(..., min_length=1, max_length=4000)

    @field_validator("goal")
    @classmethod
    def goal_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Goal cannot be empty.")
        return value

class RagRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=4000)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question cannot be empty.")
        return value

@app.post("/api/agent/run")
async def run_agent_endpoint(
    req: AgentRequest,
    request: Request,
):
    try:
        is_local_request = (
            request.client is not None
            and ip_address(request.client.host).is_loopback
        )
    except ValueError:
        is_local_request = False
    if not is_local_request:
        raise HTTPException(
            status_code=403,
            detail="Agent execution is only available from this computer.",
        )

    try:
        # Run the ReAct agent with the user's goal
        result = await run_react_agent(req.goal)
        return {"status": "success", "result": result}
    except Exception as e:
        logger.exception("Agent execution failed")
        raise HTTPException(status_code=500, detail="Agent execution failed.") from e

@app.post("/api/rag/query")
async def run_rag_endpoint(req: RagRequest):
    try:
        # Run the RAG pipeline query
        answer = await query_rag(req.question)
        return {"status": "success", "answer": answer}
    except Exception as e:
        logger.exception("RAG query failed")
        raise HTTPException(status_code=500, detail="RAG query failed.") from e

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serves the unified DevAgent Control Center UI with quick-test examples"""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>DevAgent Core — Control Center</title>
        <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-zinc-950 text-zinc-100 font-sans antialiased min-h-screen flex flex-col items-center py-10 px-4">
        
        <!-- Header -->
        <header class="w-full max-w-4xl mb-8 flex items-center justify-between border-b border-zinc-800 pb-4">
            <div>
                <h1 class="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
                    ⚡ DevAgent Core
                </h1>
                <p class="text-sm text-zinc-400">Autonomous ReAct Agent & Local Vector RAG Engine</p>
            </div>
            <div class="flex items-center gap-2">
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-950 text-emerald-400 border border-emerald-800">
                    ● Ollama Local Active
                </span>
            </div>
        </header>

        <!-- Main Grid Container -->
        <main class="w-full max-w-4xl grid grid-cols-1 md:grid-cols-2 gap-6">
            
            <!-- Card 1: Autonomous ReAct Agent -->
            <section class="bg-zinc-900 border border-zinc-800 rounded-xl p-6 flex flex-col justify-between shadow-xl">
                <div>
                    <h2 class="text-lg font-semibold text-white mb-1 flex items-center gap-2">
                        🤖 Autonomous ReAct Agent
                    </h2>
                    <p class="text-xs text-zinc-400 mb-3">Give the agent an engineering goal. It can read and write project files and check Git status.</p>
                    
                    <!-- Quick Example Suggestions -->
                    <div class="mb-4">
                        <span class="text-[10px] uppercase tracking-wider text-zinc-400 font-semibold block mb-1.5">💡 Quick Examples (Click to Load):</span>
                        <div class="flex flex-col gap-1.5">
                            <button type="button" data-agent-goal="Use write_file to create a file at docs/about_project.md with content &quot;This RAG agent project is built using Ollama, MCP, and pgvector.&quot;" class="text-left text-xs bg-zinc-950 hover:bg-zinc-800 text-indigo-300 border border-zinc-800 rounded px-2.5 py-1.5 transition truncate">
                                📝 Create doc file with write_file
                            </button>
                            <button type="button" data-agent-goal="Use run_command to check git status in the project root." class="text-left text-xs bg-zinc-950 hover:bg-zinc-800 text-indigo-300 border border-zinc-800 rounded px-2.5 py-1.5 transition truncate">
                                ⚙️ Check git status
                            </button>
                        </div>
                    </div>

                    <div class="space-y-2">
                        <label class="block text-xs font-medium text-zinc-300">Engineering Goal / Task</label>
                        <textarea id="agentGoal" rows="3" class="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-sm text-zinc-200 focus:outline-none focus:border-indigo-500 transition" placeholder="e.g. Create a status file or check git repo status..."></textarea>
                    </div>
                </div>

                <div class="mt-6">
                    <button onclick="runAgent()" id="agentBtn" class="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium py-2.5 px-4 rounded-lg text-sm transition flex items-center justify-center gap-2">
                        Execute Agent Goal
                    </button>
                    
                    <div class="mt-4">
                        <label class="block text-xs font-medium text-zinc-400 mb-1">Execution Output</label>
                        <pre id="agentOutput" class="bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-xs text-emerald-400 h-36 overflow-y-auto whitespace-pre-wrap">Awaiting execution...</pre>
                    </div>
                </div>
            </section>

            <!-- Card 2: RAG Knowledge Query -->
            <section class="bg-zinc-900 border border-zinc-800 rounded-xl p-6 flex flex-col justify-between shadow-xl">
                <div>
                    <h2 class="text-lg font-semibold text-white mb-1 flex items-center gap-2">
                        🧠 Knowledge RAG Search
                    </h2>
                    <p class="text-xs text-zinc-400 mb-3">Query your synchronized documentation vector database (`pgvector`) instantly.</p>
                    
                    <!-- Quick Example Suggestions -->
                    <div class="mb-4">
                        <span class="text-[10px] uppercase tracking-wider text-zinc-400 font-semibold block mb-1.5">💡 Quick Examples (Click to Load):</span>
                        <div class="flex flex-col gap-1.5">
                            <button onclick="setRagQuestion('What is this project built using?')" class="text-left text-xs bg-zinc-950 hover:bg-zinc-800 text-cyan-300 border border-zinc-800 rounded px-2.5 py-1.5 transition truncate">
                                🔍 Ask about project stack
                            </button>
                            <button onclick="setRagQuestion('How is PostgreSQL configured?')" class="text-left text-xs bg-zinc-950 hover:bg-zinc-800 text-cyan-300 border border-zinc-800 rounded px-2.5 py-1.5 transition truncate">
                                📊 Ask about database setup
                            </button>
                        </div>
                    </div>

                    <div class="space-y-2">
                        <label class="block text-xs font-medium text-zinc-300">Ask a Question</label>
                        <input type="text" id="ragQuestion" class="w-full bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-sm text-zinc-200 focus:outline-none focus:border-indigo-500 transition" placeholder="e.g. How is PostgreSQL configured?">
                    </div>
                </div>

                <div class="mt-6">
                    <button onclick="runRag()" id="ragBtn" class="w-full bg-zinc-800 hover:bg-zinc-700 text-white font-medium py-2.5 px-4 rounded-lg text-sm transition flex items-center justify-center gap-2">
                        Query Knowledge Base
                    </button>
                    
                    <div class="mt-4">
                        <label class="block text-xs font-medium text-zinc-400 mb-1">Retrieved Answer</label>
                        <pre id="ragOutput" class="bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-xs text-cyan-400 h-36 overflow-y-auto whitespace-pre-wrap">Awaiting query...</pre>
                    </div>
                </div>
            </section>

        </main>

        <!-- Footer -->
        <footer class="mt-12 text-xs text-zinc-500">
            DevAgent Core &bull; Local-First Architecture &bull; Powered by FastAPI, pgvector & Ollama
        </footer>

        <!-- Frontend JavaScript Logic -->
        <script>
            document.querySelectorAll('[data-agent-goal]').forEach(button => {
                button.addEventListener('click', () => setAgentGoal(button.dataset.agentGoal));
            });

            function setAgentGoal(goalText) {
                document.getElementById('agentGoal').value = goalText;
            }

            function setRagQuestion(questionText) {
                document.getElementById('ragQuestion').value = questionText;
            }

            async function runAgent() {
                const goal = document.getElementById('agentGoal').value;
                const btn = document.getElementById('agentBtn');
                const output = document.getElementById('agentOutput');
                
                if (!goal.trim()) {
                    alert('Please enter a goal for the agent.');
                    return;
                }
                btn.disabled = true;
                btn.textContent = 'Agent Running... (Check Terminal for Steps)';
                output.textContent = '🤖 Agent is reasoning and executing tools... Please wait.';

                try {
                    const response = await fetch('/api/agent/run', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ goal: goal })
                    });
                    const data = await response.json();
                    if (response.ok && data.status === 'success') {
                        output.textContent = data.result;
                    } else {
                        output.textContent = 'Error: ' + (data.detail || JSON.stringify(data));
                    }
                } catch (err) {
                    output.textContent = 'Network Error: ' + err.message;
                } finally {
                    btn.disabled = false;
                    btn.textContent = 'Execute Agent Goal';
                }
            }

            async function runRag() {
                const question = document.getElementById('ragQuestion').value;
                const btn = document.getElementById('ragBtn');
                const output = document.getElementById('ragOutput');
                
                if (!question.trim()) {
                    alert('Please enter a question.');
                    return;
                }

                btn.disabled = true;
                btn.textContent = 'Querying Vector DB...';
                output.textContent = '🧠 Retrieving vector chunks from PostgreSQL...';

                try {
                    const response = await fetch('/api/rag/query', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ question: question })
                    });
                    const data = await response.json();
                    if (response.ok && data.status === 'success') {
                        output.textContent = data.answer;
                    } else {
                        output.textContent = 'Error: ' + (data.detail || JSON.stringify(data));
                    }
                } catch (err) {
                    output.textContent = 'Network Error: ' + err.message;
                } finally {
                    btn.disabled = false;
                    btn.textContent = 'Query Knowledge Base';
                }
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(
        content=html_content,
        headers={"Cache-Control": "no-store"},
    )