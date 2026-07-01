from langgraph.graph import START, StateGraph, MessagesState, END
from langgraph.graph.message import add_messages
from langchain_core.output_parsers import StrOutputParser
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field
from langgraph.prebuilt import tools_condition, ToolNode
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Annotated
from typing_extensions import TypedDict
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
import json

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from langchain_openrouter import ChatOpenRouter

import re
import sqlite3

load_dotenv()




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

# define llm


# nodes
def select_tables(state: AgentState) -> dict:
    model = ChatOpenRouter(
        model="cohere/north-mini-code:free",
        temperature=0,
    )

    question = state["question"]
    system_prompt = """You are an AI Analyst at ACB Bank. Your task is to read the user's question and determine which database tables are required to generate the SQL query.
                     Below is the list of available tables and their brief descriptions
                        `customers`: Thông tin khách hàng cá nhân và doanh nghiệp
                        `accounts`: Tài khoản ngân hàng của khách hàng
                        `transactions`: Lịch sử giao dịch
                        `loan_products`: Danh mục sản phẩm vay của ngân hàng
                        `loans`: Hợp đồng vay của khách hàng"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{question}")
    ])
    chain = prompt | model.with_structured_output(TableSelection)
    response = chain.invoke({"question": question})
    return {"selected_tables": response.tables}


def inject_schema(state: AgentState) -> str:
    selected_tables = state["selected_tables"]
    schema_context  = []

    with open ('schema.json','r') as file:
        full_schema = json.load(file)
    
    tables_schema = full_schema.get("tables", {})
    for table in selected_tables:
        if table in tables_schema:
            table_info = tables_schema[table]

            description = table_info.get("description","N/A")
            columns = table_info.get("columns",{})

            cols_list = []
            for col_name, col_meta in columns.items():
                col_type = col_meta.get("type", "N/A")
                pk = "Primary Key" if col_meta.get("pk") else ""
                nullable = "Nullable" if col_meta.get("nullable") else ""
                fk = col_meta.get("fk","None")
                col_description = col_meta.get("description", "N/A")

                cols_list.append(f"  - {col_name} ({col_type}) {pk}, Foreign Key: {fk} {nullable}, {col_description}")
                
            columns_info = "\n".join(cols_list)
            
            table_str = (
                f"--- TABLE: {table} ---\n"
                f"Mô tả: {description}\n"
                f"Cột dữ liệu:\n{columns_info}\n"
            )    
            schema_context.append(table_str)
        
        else:
            # tables not existed
            print(f"Error: Table {table} not found.")

    return {"schema_context": "\n".join(schema_context)}


def select_few_shots(state: AgentState) -> dict:
    # read few shot examples json
    with open ('few_shot_examples.json','r') as file:
        data = json.load(file)
    examples = data["examples"]
    corpus = [ex["question"] for ex in examples]

    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(corpus)

    question = state["question"]
    question_vector = vectorizer.transform([question]) # ham transform nhan iterable list

    similarities = cosine_similarity(question_vector, X).flatten()
    top_indices = similarities.argsort()[-3:][::-1]

    few_shot_list = []

    for i in top_indices:
        ex = examples[i]
        few_shot_list.append(
            f"--- Example {ex['id']} ({ex['category']}) ---\n"
            f"Question: {ex['question']}\n"
            f"SQL:\n{ex['sql']}\n"
        )
    few_shot_context = "\n".join(few_shot_list)
    return {"few_shot_context": few_shot_context}
    

def generate_sql(state: AgentState) -> dict:
    message = state.get("messages",[])
    model = ChatOpenRouter(
        model="cohere/north-mini-code:free",
        temperature=0,
    )
    question = state["question"]
    schema_context = state["schema_context"]
    few_shot_context = state["few_shot_context"]
    validation_error = state.get("validation_error","") # case try 1st time
    retry_count = state.get("retry_count",0)
    
    system_prompt = (
        "You are an expert SQL developer for ACB Bank's SQLite database. Your task is to convert a user's Vietnamese question into a correct SQLite SELECT query.\n"
        
        "=== SCHEMA CONTEXT===\n"
        "{schema_context}\n\n"
        
        "=== FEW-SHOT EXAMPLES ===\n"
        "{few_shot_context}\n\n"
        
        "=== REQUIREMENTS ===\n"
        "1. Only return pure SQL query. No explanation, no markdown, do not wrap in ```sql).\n"
        "2. The query must start with either SELECT or WITH.\n"
        "3. Only transactions with status = 'completed' are considered valid unless the user explicitly specifies otherwise.\n"
    )

    error_prompt = (
            "\n=== WARNING: YOUR PREVIOUS SQL QUERY WAS INVALID ===\n"
            f"{validation_error}\n"
            "Hãy phân tích kỹ lỗi trên, đối chiếu lại với Schema và Business Rules để sửa lại câu lệnh SQL cho đúng.\n"
        )    
    input_variables = {
        "schema_context": schema_context,
        "few_shot_context": few_shot_context,
        "chat_history": message,
        "question": question
    }
    if retry_count > 0:
        system_prompt = system_prompt + error_prompt
        input_variables["validation_error"] = validation_error

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "generate a SQL query for the following question: {question}")
    ])
    chain = prompt_template | model | StrOutputParser()

    sql = chain.invoke(input_variables)
    return {"sql": sql}


def validate_sql(state: AgentState) -> list[dict]:
    sql = state["sql"]
    selected_tables = state["selected_tables"]
    retry_count = state.get("retry_count",0) + 1

    # LAYER 1: SAFETY CHECK
    if sql.strip().upper().split()[0] not in ["SELECT", "WITH"]:
        print ("Layer 1 failed. Query must start with SELECT or WITH ")
        return {
            "validation_error": "Query must start with SELECT or WITH.", # k rretry
            "retry_count": 10 # qua fallback 
        }
    sql = sql.rstrip().rstrip(";") # bo ; 
    if "LIMIT" not in sql.upper():
        sql = f"{sql} LIMIT 100"
        print("tự động thêm LIMIT 100 vào query.")


    # LAYER 3: SCHEMA VALIDATION
    allowed_tables = set(selected_tables)
    print(allowed_tables)
    extracted_tables = re.findall(r"\b(?:from|join)\s+([a-zA-Z0-9_]+)", sql, re.IGNORECASE)
    for table in extracted_tables:
        if table.lower() not in allowed_tables:
            print(f"Layer 3 failed: Table '{table}' does not exist.")
            return {
                "validation_error": f"Table '{table}' does not exist. Valid tables: {', '.join(allowed_tables)}.",
                "retry_count": retry_count,
                "sql": sql 
            }
    # LAYER 4: EXPLAIN QUERY PLAN
    conn = sqlite3.connect("acb_mock.db")
    try:
        
        conn.execute(f'EXPLAIN QUERY PLAN {sql}')
        return {
            "validation_error": "",
            "sql": sql
        }
    except sqlite3.OperationalError as e:
        error_msg = str(e)
        print (f"error: {e}")
        return {
            "validation_error": error_msg ,
            "retry_count": 0, # reset 
            "sql": sql
        }
    finally:
        if conn:
            conn.close()

def route_after_validate(state: AgentState):
    error = state.get("validation_error", "")
    retry_count = state.get("retry_count", 0)

    if error == "":
        print("Valid SQL. Routing to execute_sql.")
        return "execute_sql"
    if retry_count < 3:
        print (f"Invalid SQL. Retry {retry_count}/3). Routing to generate_sql.")
        return "generate_sql"
    print("Exceeded 3 retry attempts. ROuting to fallback_response.")
    return "fallback"


def execute_sql(state: AgentState) -> list[dict]:
    sql = state["sql"]
    conn = None
    try:
        conn = sqlite3.connect(
            "file:acb_mock.db?mode=ro",
            uri=True,
            timeout=5,
            check_same_thread=False
        )
        cursor = conn.execute(sql)
        columns = [c[0] for c in cursor.description]

        rows = cursor.fetchmany(50)
        results = [
            dict(zip(columns, row)) for row in rows
        ]
    except sqlite3.Error as e:
        print ("error when executing sql")
        results = [{"error": str(e)}]
    finally:
        if conn:
            conn.close()
    return {"sql_result": results}


def format_response(state: AgentState) -> str:
    question = state["question"]
    sql = state["sql"]
    sql_result = state["sql_result"]

    model = ChatOpenRouter(
        model="cohere/north-mini-code:free",
        temperature=0,
    )

    system_prompt = (   
        "You are a professional internal AI Assistant for ACB Bank.n"
        "Your task is to read the raw SQL query results and rewrite them into a natural, clear, and polite Vietnamese response for bank employees.\n\n"
        
        "=== SYSTEM INPUT ===\n"
        "• Employee's question: {question}\n"
        "• Executed SQL query: {sql}\n"
        "• Raw SQL result (list of records): {sql_result}\n\n"
        
        "=== RESPONSE RULES ===\n"
        "1. Answer the employee's question directly. Never fabricate information or numbers that are not present in the SQL result.\n"
        "2. If the SQL result is empty (an empty list []), politely inform the employee that no matching data was found in the system.\n"
        "3. If the result contains monetary values, format them clearly (e.g., 50,000,000 VND instead of 50000000).\n"
        "4. If the result set is too large, summarize the key findings or present them as bullet points for better readability.\n"
        "5. Base your response solely on the provided SQL result. Do not make assumptions or infer missing information.\n"
        "6. Do not mention SQL, databases, or internal implementation details in your response. Present the information as if you are directly answering the employee's question."
    )

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Please aggregate the raw data above and answer the question.: {question}")
    ])
    chain = prompt_template | model | StrOutputParser()
    final_answer = chain.invoke({
        "question": question,
        "sql": sql,
        "sql_result": sql_result
    })
    return {"final_answer": final_answer, "messages": [("assistant", final_answer)]}

def fallback_response(state: AgentState) -> str:
    return {"final_answer": "error...."}

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
config = {"configurable" : {"thread_id":"s2"}}

"""user_input = {"question": "Sản phẩm vay nào có tổng dư nợ cao nhất và lãi suất của nó là bao nhiêu?"}
result = graph.invoke(user_input, config=config)

print("==== q1")
print(result["final_answer"])

user_input = {"question": "Thời hạn tối đa?"}
result = graph.invoke(user_input, config=config)

print("==== q2")
print(result["final_answer"])
"""




if __name__ == "__main__":
    with open("test_questions.json", "r", encoding="utf-8") as f:
        test_data = json.load(f)

    questions_list = test_data.get("questions", test_data) if isinstance(test_data, dict) else test_data
    total_questions = len(questions_list)
    correct_count = 0

    print(f"Bắt đầu test {total_questions} câu...")

    for idx, item in enumerate(questions_list):
        test_config = {"configurable": {"thread_id": f"eval_session_{idx}"}}
        
        question = item["question"]
        expected_sql = item.get("expected_sql", "N/A") 
        
        print(f"\n[{idx+1}/{total_questions}] Câu hỏi: {question}")
        
        try:
            res = graph.invoke({"question": question, "retry_count": 0}, config=test_config)
            print(f"-> SQL: {res.get('sql')}")
            print(f"-> Retry count: {res.get('retry_count', 0)}")
            print(f"-> Final answer: {res.get('final_answer')}")
    
            
        except Exception as e:
            print(f"ERROR: {str(e)}")

    