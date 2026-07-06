from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from state import AgentState, TableSelection, SQLGeneration
import json
from langchain_core.messages import HumanMessage, AIMessage


from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from langchain_openrouter import ChatOpenRouter

import re
import sqlite3

load_dotenv()


def _load_few_shot_index():
 
    with open ('few_shot_examples.json','r') as f:
        data = json.load(f)
    examples = data["examples"]
    corpus = [ex["question"] for ex in examples]
 
    vectorizer = TfidfVectorizer()
    matrix = vectorizer.fit_transform(corpus)
    return examples, vectorizer, matrix
 
 
FEW_SHOT_EXAMPLES, FEW_SHOT_VECTORIZER, FEW_SHOT_MATRIX = _load_few_shot_index()

def select_tables(state: AgentState) -> dict:
    model = ChatOpenRouter(
        model="cohere/north-mini-code:free",
        temperature=0,
    )

    question = state["question"]
    chat_history = state.get("messages", [])
    system_prompt = """You are an AI Analyst at ACB Bank. Your task is to read the user's question and determine which database tables are required to generate the SQL query. Return ONLY the table names.
                        You MUST NOT:
                    - Answer the user's question.
                    - Explain your reasoning.
                    - Generate SQL.
                    - Infer any results.
                     Below is the list of available tables and their brief descriptions
                        `customers`: Thông tin khách hàng cá nhân và doanh nghiệp
                        `accounts`: Tài khoản ngân hàng của khách hàng
                        `transactions`: Lịch sử giao dịch
                        `loan_products`: Danh mục sản phẩm vay của ngân hàng
                        `loans`: Hợp đồng vay của khách hàng"""
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{question}")
    ])
    try:
        chain = prompt | model.with_structured_output(TableSelection)
        response = chain.invoke({
            "question": question,
            "chat_history": chat_history
        })
        return {"selected_tables": response.tables}
    except Exception as e:
        return {"validation_error": f"Table selection failed: {e}", "selected_tables": []}    
    
def inject_schema(state: AgentState) -> dict:
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
    question = state["question"]
    question_vector = FEW_SHOT_VECTORIZER.transform([question])
    similarities = cosine_similarity(question_vector, FEW_SHOT_MATRIX).flatten()
    top_indices = similarities.argsort()[-3:][::-1]
 
    few_shot_list = []
    for i in top_indices:
        ex = FEW_SHOT_EXAMPLES[i]
        few_shot_list.append(
            f"--- Example {ex['id']} ({ex['category']}) ---\n"
            f"Question: {ex['question']}\n"
            f"SQL:\n{ex['sql']}\n"
        )
    return {"few_shot_context": "\n".join(few_shot_list)}
    

def generate_sql(state: AgentState) -> dict:
    model = ChatOpenRouter(
        model="cohere/north-mini-code:free",
        temperature=0,
    )

    question = state["question"]
    chat_history = state.get("messages", [])

    schema_context = state["schema_context"]
    few_shot_context = state["few_shot_context"]

    validation_error = state.get("validation_error", "")
    retry_count = state.get("retry_count", 0)

    retry_instruction = ""

    if retry_count > 0:
        retry_instruction = """
        === PREVIOUS SQL FAILED ===

        Validation Error:
        {validation_error}

        Please analyze the error carefully.

        Requirements:
        - Fix ONLY the SQL.
        - Follow the provided schema.
        - Do not repeat the previous mistake.
        - Return ONLY the corrected SQL.
        """

    system_prompt = """
        You are an expert SQL developer for ACB Bank's SQLite database.

        Your task is to convert a Vietnamese banking question into a valid SQLite query.

        ========================
        DATABASE SCHEMA
        ========================

        {schema_context}

        ========================
        FEW SHOT EXAMPLES
        ========================

        {few_shot_context}

        ========================
        RULES
        ========================

        1. Return ONLY SQL.
        2. Do NOT use markdown.
        3. Do NOT explain.
        4. Query must start with SELECT or WITH.
        5. Only use tables and columns from the schema.
        6. Unless explicitly requested otherwise, only transactions with
        status = 'completed' are considered valid.

        {retry_instruction}
        """

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human","""User Question: {question}. Generate the SQLite query.""")
    ])

    chain = prompt | model | StrOutputParser()

    sql = chain.invoke({
        "schema_context": schema_context,
        "few_shot_context": few_shot_context,
        "retry_instruction": retry_instruction,
        "validation_error": validation_error,
        "question": question,
        "chat_history": chat_history,
    })

    return {"sql": sql}

def validate_sql(state: AgentState) -> dict:
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
    
    # case CTE
    mutation_keywords = [r"\bDELETE\b", r"\bUPDATE\b", r"\bINSERT\b", r"\bDROP\b", r"\bALTER\b"]
    for keyword in mutation_keywords:
        if re.search(keyword, sql, re.IGNORECASE):
            return {
                "validation_error": f"Không hỗ trợ thay đổi dữ liệu ({keyword.replace('\\b', '')}). Chỉ chấp nhận SELECT.",
                "retry_count": 10, 
            }
    
    sql = sql.rstrip().rstrip(";") # bo ; 
    if "LIMIT" not in sql.upper():
        sql = f"{sql} LIMIT 100"
        print("tự động thêm LIMIT 100 vào query.")


    # LAYER 3: SCHEMA VALIDATION
    allowed_tables = set(t.lower() for t in selected_tables)
    print(allowed_tables)
    
    normalized_sql = re.sub(r'\s+', ' ', sql)
    
    cte_names = set(t.lower() for t in re.findall(r"\b([a-zA-Z0-9_]+)\s+as\s*\(", normalized_sql, re.IGNORECASE))
    print(f"CTE: {cte_names}")
    
    extracted_tables = re.findall(r"\b(?:from|join)\s+([a-zA-Z0-9_]+)", normalized_sql, re.IGNORECASE)
    
    for table in extracted_tables:
        if table.lower() not in allowed_tables and table.lower() not in cte_names:
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
            "retry_count": retry_count, 
            "sql": sql
        }
    except sqlite3.OperationalError as e:
        error_msg = str(e)
        print (f"error: {e}")
        return {
            "validation_error": error_msg ,
            "retry_count": retry_count, 
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
        "You are a professional internal AI Assistant for ACB Bank."
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
    return {
        "final_answer": final_answer, 
        "messages": [
        HumanMessage(content=question),
        AIMessage(content=final_answer)]
    }

def fallback_response(state: AgentState):
    model = ChatOpenRouter(
        model="cohere/north-mini-code:free",
        temperature=0,
    )
    validation_error = state.get("validation_error", "")

    system_prompt = """
    You are a helpful banking AI assistant.

    Your task is to explain a technical validation error to the user in a friendly and concise way based STRICTLY on the provided error context.

    Rules:
    - NEVER mention technical terms: SQL, database, parser, schema, or internal code.
    - NEVER copy or mention any code-like names, table names, or column names that the system or AI self-created.
    - Focus only on what the user asked (the original question). If they asked about "điểm tín dụng", address "điểm tín dụng" and confirm it's unavailable. Do not talk about other random things.
    - Explain the problem in natural, polite Vietnamese.
    - Suggest how the user can rephrase or what valid information they should ask instead.
    - Keep the response under 100 words.
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human",
         "Validation error:\n{error}")
    ])

    chain = prompt | model | StrOutputParser()

    message = chain.invoke({"error": validation_error})

    return {"final_answer": message}

"""user_input = {"question": "Sản phẩm vay nào có tổng dư nợ cao nhất và lãi suất của nó là bao nhiêu?"}
result = graph.invoke(user_input, config=config)

print("==== q1")
print(result["final_answer"])

user_input = {"question": "Thời hạn tối đa?"}
result = graph.invoke(user_input, config=config)

print("==== q2")
print(result["final_answer"])
"""
    