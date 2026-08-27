from typing import Dict, List


call_memory: Dict[str, List[dict]] = {}


def get_memory(call_sid: str) -> List[dict]:
    return call_memory.get(call_sid, [])


def add_message(
    call_sid: str,
    role: str,
    content: str
):
    if call_sid not in call_memory:
        call_memory[call_sid] = []

    call_memory[call_sid].append(
        {
            "role": role,
            "content": content
        }
    )


def clear_memory(call_sid: str):
    call_memory.pop(call_sid, None)





