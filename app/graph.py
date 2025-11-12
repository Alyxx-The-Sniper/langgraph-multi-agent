# app/graph.py
import json
from typing import TypedDict, Annotated, Literal

# --- Core LangChain/LangGraph ---
from langchain_core.tools import tool
from langchain_core.messages import (
    BaseMessage, HumanMessage, ToolMessage, AIMessage
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import InMemorySaver

# --- Local Imports ---
from .llm import llm
from .tools import (
    get_order_status_tool,
    get_refund_status_tool,
    get_payment_details_tool,
    create_support_ticket_tool
)
from .prompts import (
    orders_app_prompt,
    refunds_payment_app_prompt,
    human_escalate_app_prompt,
    supervisor_prompt_ex
)

# ==============================================================================
# STEP 1: CREATE SPECIALIST "TEAM" AGENTS
# (This is your 'create_team_graph' factory)
# ==============================================================================

def create_team_graph(system_prompt: str, 
                      tools: list) -> StateGraph:
    
    class TeamState(TypedDict):
        messages: Annotated[list, add_messages]
        team_name: str

    def call_agent(state: TeamState):
        print(f"\n    [Team: {state['team_name']}]: Agent thinking...")
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            MessagesPlaceholder(variable_name="messages"),
        ])
        agent_llm = llm.bind_tools(tools, tool_choice="auto")
        chain = prompt | agent_llm
        response = chain.invoke(state)
        return {"messages": [response]}

    def call_tools(state: TeamState):
        print(f"    [Team: {state['team_name']}]: Calling tools...")
        last_message = state["messages"][-1]
        tool_map = {tool.name: tool for tool in tools}
        tool_messages = []
        for tool_call in last_message.tool_calls:
            try:
                tool_function = tool_map[tool_call["name"]]
                tool_output = tool_function.invoke(tool_call["args"])
                tool_messages.append(
                    ToolMessage(content=json.dumps(tool_output), tool_call_id=tool_call["id"])
                )
            except Exception as e:
                tool_messages.append(
                    ToolMessage(content=f"Error: {e}", tool_call_id=tool_call["id"])
                )
        return {"messages": tool_messages}

    def should_continue(state: TeamState):
        last_message = state["messages"][-1]
        if isinstance(last_message, AIMessage) and last_message.tool_calls:
            return "call_tools"
        else:
            return END

    workflow = StateGraph(TeamState)
    workflow.add_node("agent", call_agent)
    workflow.add_node("tools", call_tools)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue, {"call_tools": "tools", END: END})
    workflow.add_edge("tools", "agent")
    
    return workflow.compile()

# --- Build and Compile the Teams ---
orders_app = create_team_graph(
    orders_app_prompt,
    [get_order_status_tool]
)

refunds_payment_app = create_team_graph(
    refunds_payment_app_prompt,
    [get_refund_status_tool, get_payment_details_tool]
)

human_escalate_app = create_team_graph(
    human_escalate_app_prompt,
    [create_support_ticket_tool]
)

print("✅ Specialist Team graphs compiled.")

# ==============================================================================
# STEP 2: WRAP TEAMS IN @tool FOR THE SUPERVISOR
# ==============================================================================

@tool
def orders_team_tool(query: str) -> str:
    """Use this tool to delegate a task to the Order specialist team."""
    print(f"  [Supervisor]: Delegating to Orders Team with query: '{query}'")
    state = orders_app.invoke(
        {"messages": [HumanMessage(content=query)], "team_name": "Orders"}
    )
    return state["messages"][-1].content

@tool
def refund_payment_team_tool(query: str) -> str:
    """Use this tool to delegate a task to the Refund or Payment specialist team."""
    print(f"  [Supervisor]: Delegating to Refunds_Payment Team with query: '{query}'")
    state = refunds_payment_app.invoke(
        {"messages": [HumanMessage(content=query)], "team_name": "Refunds_Payment"}
    )
    return state["messages"][-1].content

@tool
def human_escalation_team_tool(query: str) -> str:
    """
    Use this tool to escalate a request to a human agent.
    This is for modifications (add, delete, cancellations, updates),
    or any topic not covered by the other specialist teams.
    """
    print(f"  [Supervisor]: Delegating to Human Escalation Team with query: '{query}'")
    state = human_escalate_app.invoke(
        {"messages": [HumanMessage(content=query)], "team_name": "Human_Escalation"}
    )
    return state["messages"][-1].content

# ==============================================================================
# STEP 3: DEFINE THE SUPERVISOR GRAPH
# ==============================================================================

supervisor_tools = [
    orders_team_tool,
    refund_payment_team_tool,
    human_escalation_team_tool
]

supervisor_prompt = ChatPromptTemplate.from_messages([
    ("system", supervisor_prompt_ex),
    MessagesPlaceholder(variable_name="messages"),
])

class SupervisorState(TypedDict):
    messages: Annotated[list, add_messages]

def call_supervisor_node(state: SupervisorState):
    """The main LLM call for the supervisor."""
    print("\n--- Supervisor: Analyzing Request ---")
    supervisor_llm = llm.bind_tools(supervisor_tools, tool_choice="auto")
    supervisor_chain = supervisor_prompt | supervisor_llm
    response = supervisor_chain.invoke(state)
    return {"messages": [response]}

def call_teams_node(state: SupervisorState):
    """This node executes the 'team' tools."""
    print("--- Supervisor: Executing Team Tasks ---")
    last_message = state["messages"][-1]
    tool_map = {tool.name: tool for tool in supervisor_tools}
    tool_messages = []

    for tool_call in last_message.tool_calls:
        try:
            tool_function = tool_map[tool_call["name"]]
            query = tool_call["args"].get("query")
            if query is None:
                raise ValueError("Team tool called without 'query' argument.")
            tool_output = tool_function.invoke(query) # This invokes the sub-graph
            tool_messages.append(
                ToolMessage(content=str(tool_output), tool_call_id=tool_call["id"])
            )
        except Exception as e:
            tool_messages.append(
                ToolMessage(content=f"Error executing team {tool_call['name']}: {e}", tool_call_id=tool_call["id"])
            )
    return {"messages": tool_messages}

def should_continue(state: SupervisorState) -> Literal["call_teams", END]:
    """Main router for the supervisor."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "call_teams"
    else:
        return END

# --- Build the Supervisor Graph ---
workflow = StateGraph(SupervisorState)
workflow.add_node("supervisor", call_supervisor_node)
workflow.add_node("call_teams", call_teams_node)

workflow.set_entry_point("supervisor")
workflow.add_conditional_edges("supervisor", should_continue, {"call_teams": "call_teams", END: END})
workflow.add_edge("call_teams", "supervisor")

# --- Compile the Final App ---
memory = InMemorySaver()
workflow = workflow.compile(checkpointer=memory)

print("✅ Supervisor Graph compiled. Application is ready.")