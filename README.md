# Text-to-SQL System

A robust, graph-based Text-to-SQL agentic framework built with LangGraph, designed to intelligently translate natural language questions into accurate SQL queries, execute them safely against a relational database, and synthesize human-readable answers.

---
## 1. Graph Architecture

The core of this system is a stateful graph where specialized nodes handle separate phases of the Text-to-SQL lifecycle. Conditional routing ensures that queries are automatically corrected if execution errors occur.

```text
[ START ]
           │
           ▼
   ┌───────────────┐
   │ select_tables │
   └───────┬───────┘
           │
           ▼
   ┌───────────────┐
   │ inject_schema │
   └───────┬───────┘
           │
           ▼
 ┌──────────────────┐
 │ select_few_shots │
 └───────┬──────────┘
           │
           ▼
   ┌───────────────┐                 Fail (< 3 retries)
   │  generate_sql │◄────────────────────────────────────────┐
   └───────┬───────┘                                         │
           │                                                 │
           ▼                                                 │
   ┌───────────────┐                                         │
   │  validate_sql │                                         │
   └───────┬───────┘                                         │
           │                                                 │
           ▼                                                 │
       < Router > ───────────────────────────────────────────┤
           │                                                 │
           ├─────────────────┐                               │
           │ Valid           │ Fail (≥ 3 retries)            │
           ▼                 ▼                               │
   ┌───────────────┐ ┌───────────────────┐                   │
   │  execute_sql  │ │ fallback_response │                   │
   └───────┬───────┘ └─────────┬─────────┘                   │
           │                   │                             │
           ▼                   │                             │
   ┌─────────────────┐         │                             │
   │ format_response │         │                             │
   └───────┬─────────┘         │                             │
           │                   │                             │
           ▼                   ▼                             │
       [  END  ] ◄─────────────┴─────────────────────────────┘
```

---

## 2. Setup & Execution Guide

### Prerequisites
* Python 3.12 or higher
* Access to a supported LLM Provider (e.g., OpenAI API Key)

### Running with Docker

1. **Clone the repository and navigate into it:**
   ```bash
   git clone https://github.com/bnganzzz/text-to-sql.git
   cd text-to-sql
   ```

2. **Configure environment variables:**
   Create a `.env` file in the root directory:
   ```env
   OPENROUTER_API_KEY=your_api_key_here
   ```

3. **Spin up the stack:**
   ```bash
   docker-compose up --build
   ```
   *The Chainlit dashboard will be accessible at `http://localhost:8000`.*

### Local Installation

1. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  
   ```

2. **Install requirements:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialize the Database:**
   ```bash
   python data/setup_db.py
   ```

4. **Launch the Interactive UI:**
   ```bash
   chainlit run demo.py -w
   ```
Try these questions:
* `"Liệt kê top 3 khách hàng có tổng số dư tài khoản cao nhất"`
* `"Sản phẩm vay nào có kỳ hạn lớn nhất?"`

---

## 3. Evaluation 

To assess the correctness, performance, and formatting of the generated SQL queries against standard test suites:

```bash
python eval.py
```
This script runs the query test cases from `test_questions.json` through the Compiled LangGraph workflow.

---

## 4. Limitations

- **Lack of Intent Classification (Chitchat Handling)**: The current architecture lacks an upfront intent classification mechanism. Standard greetings, casual chitchat, or out-of-scope conversational inputs are not handled natively; instead, they are routed entirely through all the nodes, which forces the LLM to inappropriately attempt schema mapping and query generation for non-database questions.