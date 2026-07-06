from state import AgentState
from langgraph.graph import START, StateGraph, END
from nodes import select_tables, inject_schema, select_few_shots, generate_sql, validate_sql, execute_sql, format_response, fallback_response, route_after_validate
from langgraph.checkpoint.memory import MemorySaver

# build graph
builder = StateGraph(AgentState)
builder.add_node("select_tables", select_tables)
builder.add_node("inject_schema", inject_schema)
builder.add_node("select_few_shots", select_few_shots)
builder.add_node("generate_sql", generate_sql)
builder.add_node("validate_sql", validate_sql)
builder.add_node("execute_sql", execute_sql)
builder.add_node("format_response", format_response)
builder.add_node("fallback_response", fallback_response)


# logic
builder.add_edge(START, "select_tables")
builder.add_edge("select_tables", "inject_schema")
builder.add_edge("inject_schema", "select_few_shots")
builder.add_edge("select_few_shots", "generate_sql")
builder.add_edge("generate_sql", "validate_sql")
builder.add_conditional_edges("validate_sql",route_after_validate, {
    "execute_sql": "execute_sql",
    "generate_sql": "generate_sql",
    "fallback": "fallback_response"
} )
builder.add_edge("execute_sql", "format_response")
builder.add_edge("format_response", END)
builder.add_edge("fallback_response", END)



checkpointer = MemorySaver() 
graph = builder.compile(checkpointer=checkpointer)
