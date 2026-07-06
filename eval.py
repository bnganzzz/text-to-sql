import json
from graph import graph

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
            break
    
            
        except Exception as e:
            print(f"ERROR: {str(e)}")
