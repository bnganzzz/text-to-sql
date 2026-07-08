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
## 🚀 Features

- **Agentic Workflow**: Managed state transitions and sophisticated query correction loops implemented via LangGraph (`graph.py`, `nodes.py`, `state.py`).
- **Interactive UI**: Clean chat interface powered by Chainlit (`demo.py`, `chainlit.md`) allowing users to interactively query databases in natural language.
- **Dynamic Few-Shot Prompting**: Uses curated few-shot examples (`few_shot_examples.json`) to boost model translation accuracy for complex schema layouts.
- **Automated DB Setup**: Streamlined seeding and instantiation scripts (`setup_db.py`, `schema.json`).
- **Rigorous Evaluation**: Validation suite (`eval.py`, `test_questions.json`) to run benchmark tests against a gold standard dataset, logging execution results (`result.txt`).
- **Production Ready**: Fully containerized using Docker and Docker Compose for easy deployment.

---

## 📁 Repository Structure

```bash
├── .dockerignore            # Specifies files to exclude from Docker images
├── .gitignore               # Standard Git ignore configurations
├── Dockerfile               # Multi-stage build definition for the application
├── docker-compose.yml       # Orchestration file for app and database services
├── requirements.txt         # Managed Python package dependencies
├── schema.json              # Structural definition of the target database schemas
├── setup_db.py              # Script to initialize, schema-map, and populate the DB
├── state.py                 # Graph state and context specifications for LangGraph
├── nodes.py                 # Business logic and LLM invocations for agent nodes
├── graph.py                 # Core routing logic and compilation of the agent workflow
├── demo.py                  # Entrypoint for the Chainlit web interface
├── chainlit.md              # Documentation/landing view rendered within Chainlit
├── few_shot_examples.json   # Curated natural-language to SQL pairings for prompt injection
├── test_questions.json      # Gold-standard evaluation questions and ground truth queries
├── eval.py                  # Benchmark script evaluating accuracy and performance
└── result.txt               # Stored metrics and outputs from evaluation runs
```

---

## 🛠️ Quick Start

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
   python setup_db.py
   ```

4. **Launch the Interactive UI:**
   ```bash
   chainlit run demo.py -w
   ```

---

## 📊 Evaluation 

To assess the correctness, performance, and formatting of the generated SQL queries against standard test suites:

```bash
python eval.py
```
This script runs the query test cases from `test_questions.json` through the Compiled LangGraph workflow.