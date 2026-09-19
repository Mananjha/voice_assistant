# Naikroop AI Voice Assistant

A browser-based voice assistant for **Naikroop**. You open a local web page, click Call, talk into your microphone, and the AI answers back in speech — using knowledge scraped from the Naikroop website.

---

## 1. Setup & How to Run It

### Requirements
- Python 3.10+ (3.11 recommended)
- Windows (pyttsx3 uses the built-in SAPI5 voice engine on Windows; other OSes need a different TTS backend)
- A Hugging Face account + API token (for the LLM)

### Step 1 — Create and activate a virtual environment
```bash
cd naikroop-ai-voice-agent
python -m venv venv
venv\Scripts\activate       
```

### Step 2 — Install dependencies
```bash
pip install -r requirements.txt
pip install pywin32           
```

### Step 3 — Configure environment variables
Copy `.env.example` to `.env` and fill in your values:
```
HF_TOKEN=your_huggingface_token

# only needed if you use the phone-call version
TWILIO_ACCOUNT_SID=your_sid         
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_PHONE_NUMBER=your_twilio_number
```
`HF_TOKEN` is required — the app will refuse to start without it, since it's used to call the Hugging Face-hosted LLM.

### Step 4 — Build the knowledge base
Before the assistant can answer questions, it needs to crawl naikroop.com and build its FAISS vector index:
```bash
python -m app.rag
```
This scrapes the site, chunks the text, embeds it with `all-MiniLM-L6-v2`, and saves the index to `data/faiss_index/`. Re-run this any time the website content changes.

### Step 5 — Start the server
```bash
uvicorn app.main:app --reload
```

### Step 6 — Open it in your browser
Go to:
```
http://127.0.0.1:8000
```
Click **Call**, allow microphone access, and start talking. The AI will greet you first, then respond to whatever you ask.

---

## 2. How Browser Communication Works

The assistant talks to your browser over **WebRTC** — the same real-time audio/video technology used by Google Meet or Zoom — rather than uploading recorded clips back and forth. This is what makes it feel like a live call instead of a chatbot with a "record" button.

### The moving parts

| Layer | What it does |
|---|---|
| **`static/index.html` + `app.js`** | The web page. Uses `getUserMedia()` to grab your microphone and `RTCPeerConnection` to open a WebRTC connection to the server. |
| **`app/main.py`** | FastAPI server. Exposes `/webrtc/offer`, which receives the browser's connection request and negotiates a WebRTC session using `aiortc` (Python's WebRTC library). |
| **`app/voice.py`** | The core voice pipeline — everything below happens here. |
| **`app/graph.py` + `app/rag.py`** | The "brain": retrieves relevant Naikroop content and asks the LLM to answer using it. |

### The call flow, step by step

1. **Connecting** — Your browser opens a WebRTC connection to the server. Two audio tracks are set up: one carrying your mic audio *to* the server, and one carrying the AI's voice *from* the server back to your speakers.

2. **Greeting** — Once the connection is confirmed active, the server waits briefly until it detects the browser is actually pulling audio frames (not just connected), then speaks a greeting.

3. **Listening** — Your mic audio arrives at the server in small ~20ms chunks. The server measures the volume (RMS) of each chunk to detect when you start and stop talking — this is a simple **Voice Activity Detection (VAD)** system. It also keeps a short "pre-roll" buffer so the very start of your sentence isn't cut off.

4. **Transcribing** — Once you stop talking (about 0.9 seconds of silence), your captured audio is resampled and sent to **Faster-Whisper**, a local speech-to-text model, which converts it into text.

5. **Thinking** — Your question is passed to a **LangGraph** pipeline (`graph.py`), which:
   - Searches the FAISS vector index for relevant chunks from the Naikroop website (RAG — retrieval-augmented generation)
   - Pulls short-term conversation memory for context
   - Sends everything to a Hugging Face-hosted LLM, which generates the answer

6. **Speaking** — The answer text is converted to speech using **pyttsx3** (a local, offline text-to-speech engine). This runs on its own dedicated background thread, since Windows' speech engine doesn't play well with being called from random async threads.

7. **Streaming back** — The generated speech audio is queued into the outgoing WebRTC audio track, which streams it to your browser in real time, and you hear the AI's reply through your speakers.

8. This repeats — after the AI finishes speaking, it starts listening again automatically, so the "call" continues like a real conversation until you hang up.

### Why WebRTC instead of simpler options
A basic approach would be: record audio in the browser → upload the file → get a reply → play it back. WebRTC instead keeps a persistent, low-latency, streaming connection open in both directions, so audio flows continuously without repeated uploads — which is what makes the interaction feel like an actual phone call rather than a slow back-and-forth.

---

## Notes
- `data/faiss_index/` is your knowledge base — rebuild it (`python -m app.rag`) whenever the Naikroop site content changes.
- `app/main1.py` is a separate, Twilio-based implementation for real phone calls — it's not used by the browser flow above.
- Keep `.env` out of version control; it holds real API credentials.


