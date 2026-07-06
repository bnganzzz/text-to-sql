from pydantic import BaseModel, Field
from typing import List, Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    question: str
    selected_tables: list[str]
    schema_context: str
    few_shot_context: str
    sql: str 
    validation_error: str
    retry_count: int
    sql_result: list[dict]
    final_answer: str
    messages: Annotated[list, add_messages]


class TableSelection(BaseModel):
    tables: List[str] = Field(description="List of tables needed to answer the question. Valid table names: customers, accounts, transactions, loan_products, loans.")

class SQLGeneration(BaseModel):
    sql: str = Field(description="A clean, executable SQL SELECT query")