import chainlit as cl
import uuid
from langgraph.checkpoint.memory import MemorySaver
from graph import graph

@cl.on_chat_start
async def on_chat_start():
    thread_id = str(uuid.uuid4())
    cl.user_session.set("config", {"configurable": {"thread_id": thread_id}})
    await cl.Message(content="HI. Tôi là Trợ lý AI nội bộ tại ACB Bank. Bạn muốn hỏi gì hôm nay?").send()


@cl.on_message  # this function will be called every time a user inputs a message in the UI
async def on_message(message: cl.Message):
    """
    This function is called every time a user inputs a message in the UI.
    It sends back an intermediate response from the tool, followed by the final answer.

    Args:
        message: The user's message.

    Returns:
        None.
    """
    config = cl.user_session.get("config")
    user_question = message.content

    inputs = {
        "question": user_question, 
        "messages": [("user", user_question)],
        "retry_count": 0
    }
    msg = cl.Message(content="")
    await msg.send()

    try: # stream
        async for output in graph.astream(inputs, config=config):
            for node_name, state_update in output.items():
                
                async with cl.Step(name=f"Node: {node_name}") as step:
                    if "selected_tables" in state_update:
                        step.output = f"Đang chọn table: {', '.join(state_update['selected_tables'])}"
                    elif "sql" in state_update:
                        step.output = f"SQL:\n```sql\n{state_update['sql']}\n```"
                    elif "validation_error" in state_update and state_update["validation_error"]:
                        step.output = f"Phát hiện lỗi validate: {state_update['validation_error']}"
                    elif "sql_result" in state_update:
                        step.output = f"Đã thực thi SQL và lấy được {len(state_update['sql_result'])} bản ghi thô."
                    else:
                        step.output = f"Đang xử lý tại node {node_name}..."
                    await step.update()
        final_state = await graph.aget_state(config)
        final_answer = final_state.values.get("final_answer", "Xin lỗi, tôi không thể xử lý câu hỏi này.")
        msg.content = final_answer

        
        await msg.update()

    except Exception as e:
        msg.content = f"ERROR {str(e)}. Try again."
        await msg.update()
    


