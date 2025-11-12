import uuid
import json
import os
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# Note: You must ensure 'graph' (workflow) is accessible for this to run.
# Import the compiled graph
try:
    from .graph import workflow #use relative path
except ImportError as e:
    print(f"⚠️  graph.py not found (Error: {e}). Using mock workflow.")
    
    # --- FIX: Added the complete MockWorkflow fallback ---
    class MockWorkflow:
        async def astream(self, *args, **kwargs):
            yield {"messages": [AIMessage(content="Mock response: Workflow not initialized.")]}
        def invoke(self, *args, **kwargs):
            return {"messages": [AIMessage(content="Mock response: Workflow not initialized.")]}
    
    workflow = MockWorkflow() # Assign the mock to the workflow variable
    # ----------------------------------------------------


# Initialize the FastAPI app
app = FastAPI(
    title="LangGraph Customer Support Agent",
    description="A multi-agent customer support system using LangGraph and FastAPI.",
    version="1.0"
) 


# --- index.html ---
# Get the absolute path to the directory containing this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

@app.get("/")
async def get_index():
    """Serves the frontend HTML file."""
    # NEW: Construct the full path to index.html
    static_file_path = os.path.join(BASE_DIR, "index.html")
    if not os.path.exists(static_file_path):
        return {"error": "index.html not found"}, 404
    return FileResponse(static_file_path)


# NEW: Configure and add CORS middleware to allow the HTML frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all origins for simple demo/development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    """Request model for the chat endpoint."""
    query: str
    thread_id: str | None = None

# --- Asynchronous Streaming Endpoint ---
@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    Main chat endpoint.
    Streams back a JSON object for each step of the graph.
    """
    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    # Initial input for the graph
    inputs = {"messages": [HumanMessage(content=request.query)]}
    
    async def stream_generator():
        """Pushes graph events to the client."""
        print(f"\n🚀 Starting stream for thread: {thread_id}")
        yield f"event: new_thread\ndata: {json.dumps({'thread_id': thread_id})}\n\n"
        
        # Use .astream() to stream back all intermediate steps
        try:
            async for step in workflow.astream(inputs, config=config, stream_mode="values"):
                last_message = step["messages"][-1]
                event_data = {"thread_id": thread_id}
                
                if isinstance(last_message, AIMessage):
                    if last_message.tool_calls:
                        # Supervisor is planning to call a team
                        event = "supervisor_plan"
                        event_data["team"] = last_message.tool_calls[0]['name']
                        event_data["query"] = last_message.tool_calls[0]['args'].get('query', 'N/A')
                    else:
                        # Supervisor has a final answer
                        event = "final_answer"
                        event_data["content"] = last_message.content
                
                elif isinstance(last_message, ToolMessage):
                    # A team has reported back to the supervisor
                    event = "team_report"
                    event_data["content"] = last_message.content
                    
                else:
                    # Filter out the initial human message from showing as "unknown"
                    if not isinstance(last_message, HumanMessage):
                        event = "unknown_step"
                        event_data["content"] = str(last_message)
                    else:
                        continue # Skip the initial human message

                # Send the event in Server-Sent-Event (SSE) format
                yield f"event: {event}\ndata: {json.dumps(event_data)}\n\n"
        except Exception as e:
            error_data = {"error": str(e), "message": "An error occurred during agent execution."}
            yield f"event: error\ndata: {json.dumps(error_data)}\n\n"

        print(f"\n🏁 Stream complete for thread: {thread_id}")

    # Return the streaming response
    return StreamingResponse(stream_generator(), media_type="text/event-stream")

# --- Simple (non-streaming) endpoint for quick tests ---
@app.post("/chat/invoke")
def chat_invoke(request: ChatRequest) -> dict:
    """
    Simpler endpoint that just runs the graph and returns the
    final response. Good for simple tests.
    """
    thread_id = request.thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    inputs = {"messages": [HumanMessage(content=request.query)]}
    
    print(f"\n🚀 Invoking graph for thread: {thread_id}")
    
    # .invoke() runs the whole graph and returns only the final state
    final_state = workflow.invoke(inputs, config=config)
    
    final_answer = final_state["messages"][-1].content
    print(f"\n🏁 Invocation complete for thread: {thread_id}")
    
    return {"response": final_answer, "thread_id": thread_id}

# --- Health Check ---
@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}

# REMOVED the `if __name__ == "__main__":` block
# to prevent import errors.
# ALWAYS run locally from the root folder with:
# uvicorn app.api:app --reload