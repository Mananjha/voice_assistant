import json
from pathlib import Path
from datetime import datetime

from fastapi import (
    FastAPI,
    Request,
    Form
)

from fastapi.responses import Response

from twilio.twiml.voice_response import (
    VoiceResponse,
    Gather
)

from app.graph import ask_agent
from app.memory import clear_memory


app = FastAPI(
    title="Naikroop AI Voice Enquiry Assistant"
)


CALLS_FILE = Path("data/calls.json")


def load_calls():

    if not CALLS_FILE.exists():
        return []

    try:
        return json.loads(
            CALLS_FILE.read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return []


def save_calls(calls):

    CALLS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    CALLS_FILE.write_text(
        json.dumps(
            calls,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )


@app.get("/")
def home():

    return {
        "message": "Naikroop AI Voice Enquiry Assistant",
        "status": "running"
    }

@app.get("/health")
def health():

    return {
        "status": "ok"
    }


@app.post("/voice")
async def voice(request: Request):

    response = VoiceResponse()

    gather = Gather(
        input="speech",
        action="/process-speech",
        method="POST",
        speech_timeout="auto",
        language="en-IN"
    )

    gather.say(
        "Hello. You are speaking with "
        "Naikroop's AI assistant. "
        "How can I help you?",
        voice="alice",
        language="en-IN"
    )

    response.append(gather)
    
    response.redirect("/voice")

    # response.say(
    #     "I didn't hear anything. "
    #     "Please call again if you need assistance.",
    #     voice="alice",
    #     language="en-IN"
    # )

    return Response(
        content=str(response),
        media_type="application/xml"
    )


@app.post("/process-speech")
async def process_speech(
    request: Request,
    SpeechResult: str = Form(""),
    CallSid: str = Form("")
):

    print()
    print("=" * 60)
    print("CALL SID:", CallSid)
    print("USER:", SpeechResult)
    print("=" * 60)
    
    response = VoiceResponse()

    question = SpeechResult.strip()

    if not question:

        gather = Gather(
            input="speech",
            action="/process-speech",
            method="POST",
            speech_timeout="auto",
            language="en-IN"
        )

        gather.say(
            "Sorry, I didn't understand that. "
            "Could you please repeat your question?",
            voice="alice",
            language="en-IN"
        )

        response.append(gather)

        return Response(
            content=str(response),
            media_type="application/xml"
        )

    try:

        answer = ask_agent(
            CallSid,
            question
        )
        
        print("AI:", answer)

    except Exception as e:

        print(
            "Agent error:",
            str(e)
        )

        answer = (
            "I'm sorry, I'm having trouble "
            "answering that right now. "
            "Please contact the Naikroop team "
            "for assistance."
        )

    gather = Gather(
        input="speech",
        action="/process-speech",
        method="POST",
        speech_timeout="auto",
        language="en-IN"
    )

    gather.say(
        answer,
        voice="alice",
        language="en-IN"
    )

    response.append(gather)

    return Response(
        content=str(response),
        media_type="application/xml"
    )


@app.post("/call-complete")
async def call_complete(
    request: Request
):

    form = await request.form()

    call_sid = form.get(
        "CallSid",
        ""
    )

    calls = load_calls()

    from app.memory import get_memory

    conversation = get_memory(
        call_sid
    )

    record = {
        "call_sid": call_sid,
        "timestamp": datetime.utcnow().isoformat(),
        "conversation": conversation
    }

    calls.append(record)

    save_calls(calls)

    clear_memory(call_sid)

    return {
        "status": "saved",
        "call_sid": call_sid
    }


@app.get("/calls")
def get_calls():

    return load_calls()










