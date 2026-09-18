import asyncio
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from aiortc import RTCPeerConnection, RTCSessionDescription

from app.graph import ask_agent
from app.voice import VoiceSession

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Naikroop AI Voice Enquiry Assistant",
    description="Browser-based AI voice enquiry assistant for Naikroop",
    version="2.0.0",
)

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)

class QuestionRequest(BaseModel):
    session_id: str
    question: str


@app.post("/ask")
def ask_question(request: QuestionRequest):

    answer = ask_agent(
        request.session_id,
        request.question,
    )

    return {
        "answer": answer
    }

@app.get("/")
def home():

    return FileResponse(
        STATIC_DIR / "index.html"
    )

peer_connections = {}
voice_sessions = {}


class WebRTCOffer(BaseModel):
    sdp: str
    type: str


@app.post("/webrtc/offer")
async def webrtc_offer(offer: WebRTCOffer):

    session_id = str(uuid.uuid4())

    print()
    print("========================================")
    print("NEW WEBRTC CALL")
    print(f"Session ID: {session_id}")
    print("========================================")

    pc = RTCPeerConnection()

    peer_connections[session_id] = pc

    voice_session = VoiceSession(
        session_id
    )

    voice_sessions[session_id] = voice_session

    @pc.on("track")
    def on_track(track):

        print(
            f"Received track: {track.kind}"
        )

        if track.kind == "audio":

            async def receive_audio():

                try:

                    while voice_session.running:

                        frame = await track.recv()

                        await voice_session.process_audio(
                            frame
                        )

                except Exception as e:

                    print(
                        "Audio receive stopped:"
                    )

                    print(
                        repr(e)
                    )

            asyncio.create_task(
                receive_audio()
            )

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():

        print(
            "WebRTC connection state:",
            pc.connectionState
        )

        if pc.connectionState == "connected":

            print(
                "WebRTC connected."
            )

            asyncio.create_task(
                voice_session.send_greeting()
            )

        elif pc.connectionState in [
            "failed",
            "closed",
            "disconnected",
        ]:

            await cleanup_session(
                session_id
            )

    await pc.setRemoteDescription(
        RTCSessionDescription(
            sdp=offer.sdp,
            type=offer.type,
        )
    )

    pc.addTrack(
        voice_session.output_track
    )

    answer = await pc.createAnswer()

    await pc.setLocalDescription(
        answer
    )

    return {
        "session_id": session_id,
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type,
    }

@app.post(
    "/webrtc/{session_id}/close"
)
async def close_call(
    session_id: str
):

    await cleanup_session(
        session_id
    )

    return {
        "success": True
    }


async def cleanup_session(
    session_id: str
):

    print(f"Cleaning up session: {session_id}")

    voice_session = voice_sessions.pop(
        session_id,
        None
    )

    if voice_session:

        try:

            await voice_session.close()

        except Exception as e:

            print(
                "Voice session close error:",
                repr(e)
            )

    pc = peer_connections.pop(
        session_id,
        None
    )

    if pc:

        try:

            await pc.close()

        except Exception as e:

            print(
                "Peer close error:",
                repr(e)
            )