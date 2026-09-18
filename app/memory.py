from typing import Dict, List


session_memory: Dict[str, List[dict]] = {}


def get_memory(session_id: str) -> List[dict]:
    return session_memory.get(session_id, [])


def add_message(
    session_id: str,
    role: str,
    content: str
):
    if session_id not in session_memory:
        session_memory[session_id] = []

    session_memory[session_id].append(
        {
            "role": role,
            "content": content
        }
    )


def clear_memory(session_id: str):
    session_memory.pop(session_id, None)





