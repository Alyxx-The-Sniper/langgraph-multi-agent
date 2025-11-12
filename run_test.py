# run_test.py
import uuid
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# Import the 'app' from the app.graph module
from app.graph import app

def run_query(query: str, thread_id: str):
    """
    Runs the graph for a given query and thread_id.
    """
    print(f"\n=================================================================")
    print(f"🚀 EXECUTING QUERY: \"{query}\" (Thread: {thread_id})")
    print(f"=================================================================\n")
    
    config = {"configurable": {"thread_id": str(thread_id)}}
    initial_state = {"messages": [HumanMessage(content=query)]}
    
    for step in app.stream(initial_state, config=config, stream_mode="values"):
        if "messages" not in step or not step["messages"]:
            continue
            
        last_message = step["messages"][-1]

        if isinstance(last_message, AIMessage):
            if last_message.tool_calls:
                print("--- Supervisor: Planning ---")
                for tc in last_message.tool_calls:
                    print(f"  > Planning to call: {tc['name']}")
                    print(f"    - Query: {tc['args'].get('query')}")
            else:
                print(f"\n✅ --- Supervisor: Final Answer ---")
                print(last_message.content)
                
        elif isinstance(last_message, ToolMessage):
            print("--- Supervisor: Received Report ---")
            print(f"  > Report: {last_message.content}")

    print(f"\n=================================================================")
    print(f"🏁 RUN COMPLETE FOR THREAD: {thread_id}")
    print(f"=================================================================\n")

if __name__ == "__main__":
    # Create a single thread ID for the test run
    thread_id = f"test_thread_{uuid.uuid4()}"
    
    # Test 1: Order Status
    run_query("Hi, I need to check the status of my order, tracking number 7.", thread_id)
    
    # # Test 2: Escalation (on the SAME thread)
    # run_query("Okay, thanks. Now I need to cancel that order.", thread_id)
    
    # # Test 3: Refund Status (on the SAME thread)
    # run_query("One last thing, what's the status of my refund for order 4?", thread_id)