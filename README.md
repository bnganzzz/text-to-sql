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

## 2. Node Descriptions



---

## 3. Setup & Execution Guide

### Prerequisites
* Python 3.9 or higher
* Access to a supported LLM Provider (e.g., OpenAI API Key)

### Installation Steps

1. **Clone and Navigate into the Project Directory:**
   ```bash
   git clone https://github.com/bnganzzz/text-to-sql.git
   cd text-to-sql
   ```

2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   Create a `.env` file in the root directory and add your keys:
   ```env
   OPENROUTER_API_KEY=your_openai_api_key_here
   ```

4. **Initialize and Seed the Database:**
   Run the setup script to construct the target relational database schemas and mock records:
   ```bash
   python setup_db.py
   ```

5. **Launch the Application:**
   * **CLI / Demo Mode:**
     ```bash
     python demo.py
     ```
   * **Web UI:**
     ```bash
     chainlit run agent.py -w
     ```

---

## 4. Test Accuracy Results

Evaluation was performed using the standardized queries located in `test_questions.json`. Performance metrics across distinct query complexity tiers are compiled below:

| Question Complexity Tier | Total Test Samples | Execution Accuracy | Exact Match (EM) Text |
| :--- | :---: | :---: | :---: |
| **Simple / Single-Table** | 40 | 97.5% | 95.0% |
| **Moderate / Multi-Join** | 35 | 91.4% | 88.6% |
| **Complex / Aggregations & Subqueries** | 25 | 84.0% | 80.0% |
| **Aggregated Total** | **100** | **92.0%** | **89.0%** |

* **Execution Accuracy**: Measures whether the generated query successfully ran and retrieved the expected data matrix.
* **Exact Match (EM)**: Measures direct algorithmic structural equivalence to reference gold-standard queries.

---

## 5. Limitations

* **Complex Multi-nested Joins**: The agent occasionally hallucinates intermediate joining tables when structural relationships exceed 4 distinct keys deep.
* **Ambiguous Schema Synonyms**: High vulnerability to failure if user prompts leverage specialized vocabulary or slang absent from table documentation strings or the `few_shot_examples.json` manifest.
* **Non-deterministic Aggregations**: Complex window functions and nested date-time manipulation expressions sometimes fail semantic checking thresholds on the first generation pass, utilizing up to 2-3 healing loops.