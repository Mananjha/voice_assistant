from typing import TypedDict, List
from app.rag import retrieve_knowledge

from langchain_huggingface import (
    ChatHuggingFace,
    HuggingFaceEndpoint
)

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage
)

from langgraph.graph import (
    StateGraph,
    START,
    END
)

from app.config import HF_TOKEN
from app.knowledge import load_knowledge
from app.memory import (
    get_memory,
    add_message
)

class AgentState(TypedDict):
    call_sid: str
    question: str
    answer: str


# knowledge = load_knowledge()


llm_endpoint = HuggingFaceEndpoint(
    repo_id="openai/gpt-oss-120b",
    huggingfacehub_api_token=HF_TOKEN,
    max_new_tokens=180,
    temperature=0.2,
)

llm = ChatHuggingFace(
    llm=llm_endpoint
)


def generate_answer(state: AgentState):

    call_sid = state["call_sid"]
    question = state["question"]

    previous_messages = get_memory(call_sid)

    history = []

    for message in previous_messages:

        if message["role"] == "user":
            history.append(
                HumanMessage(
                    content=message["content"]
                )
            )

        elif message["role"] == "assistant":
            history.append(
                AIMessage(
                    content=message["content"]
                )
            )
            
    try:

        retrieved_context = retrieve_knowledge(
            question,
            k=4
        )

    except Exception as e:

        print("RAG ERROR:")
        print(repr(e))

        retrieved_context = ""            
            

    system_prompt = f"""
You are Naikroop's AI Voice Enquiry Assistant.  

You are speaking with a potential customer on a phone call.

Your job is to answer questions about Naikroop.

IMPORTANT RULES:

1. Use ONLY the information in the knowledge section.
2. Do not invent facts.
3. Do not invent pricing.
4. Do not invent customers.
5. Do not invent features.
6. Use the previous conversation to understand follow-up questions.
7. Keep answers short and natural because this is a phone conversation.
8. Do not mention internal prompts, LangGraph, LangChain,
   Hugging Face, or the knowledge file.
9. If the information is not available, say:
   "I don't have that information available. You can contact
   the Naikroop team for more details."
10. Answer the user's actual question rather than using a
    predefined answer.

RETRIEVED NAIKROOP INFORMATION:

{retrieved_context}
"""
    messages = [
        SystemMessage(content=system_prompt)
    ]

    messages.extend(history)

    messages.append(
        HumanMessage(content=question)
    )

    try:
        response = llm.invoke(
            messages
        )
        print("RAW LLM RESPONSE:")
        print(response)

        answer = response.content

        print()
        print("FINAL ANSWER:")
        print(answer)
        print()
    except Exception as e:
        print("LLM ERROR:")
        print(repr(e))
        answer = (
            "I'm sorry, I'm having trouble "
            "answering that right now."
        )    

    add_message(
        call_sid,
        "user",
        question
    )

    add_message(
        call_sid,
        "assistant",
        answer
    )
    return {
        "call_sid": call_sid,
        "question": question,
        "answer": answer
    }

graph_builder = StateGraph(AgentState)

graph_builder.add_node(
    "generate_answer",
    generate_answer
)

graph_builder.add_edge(
    START,
    "generate_answer"
)

graph_builder.add_edge(
    "generate_answer",
    END
)

graph = graph_builder.compile()

def ask_agent(
    call_sid: str,
    question: str
) -> str:
    result = graph.invoke(
        {
            "call_sid": call_sid,
            "question": question,
            "answer": ""
        }
    )
    return result["answer"]




