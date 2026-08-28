# Naikroop AI Voice Agent

An AI-powered voice enquiry agent for Naikroop.

The agent allows users to call a phone number and ask questions about Naikroop. It uses the Naikroop website as its knowledge source and uses Retrieval-Augmented Generation (RAG) to provide relevant answers.

The agent also maintains short-term conversation memory during the current phone call so users can ask follow-up questions naturally.

---

## Features

- Voice-based interaction through Twilio
- Speech-to-text using Twilio's speech recognition
- Natural language responses using an LLM
- Retrieval-Augmented Generation (RAG)
- Naikroop website as the knowledge source
- FAISS vector database for similarity search
- Hugging Face embeddings
- Hugging Face LLM
- LangChain for LLM and RAG integration
- LangGraph for agent workflow
- FastAPI backend
- Short-term memory for the current call
- Follow-up questions supported within the same call
- No permanent conversation memory

---

## Architecture

Voice → Agent → RAG/Memory → Voice response

Python
FastAPI — backend/API
Uvicorn — FastAPI server
Twilio — voice calls & speech input/output
LangChain — LLM & RAG integration
LangGraph — agent workflow
Hugging Face — LLM & embeddings
GPT-OSS-120B — language model
Sentence Transformers / all-MiniLM-L6-v2 — embeddings
FAISS — vector database
BeautifulSoup4 — website content extraction
Requests — website fetching
LangChain Text Splitters — document chunking
Short-Term Memory — current CallSid conversation context
TryCloudflare (Cloudflare Tunnel) — local development tunnel to Twilio
Naikroop Website — knowledge source (naikroop.com)

Setup and Run
1. Clone the Repository

Clone the project from GitHub:

git clone <YOUR_GITHUB_REPOSITORY_URL>
cd naikroop-ai-voice-agent
2. Create a Virtual Environment

Create a Python virtual environment:

python -m venv venv

Activate the virtual environment:

venv\Scripts\activate

After activation, the terminal should show:

(venv)
3. Install Dependencies

Install all required Python packages:

pip install -r requirements.txt

The project uses:

FastAPI
Uvicorn
LangChain
LangGraph
Hugging Face
Sentence Transformers
FAISS
BeautifulSoup4
Requests
Twilio
4. Configure Environment Variables

Create a .env file in the project root:

naikroop-ai-voice-agent/
│
├── app/
├── data/
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md

Add the required credentials to .env:

HF_TOKEN=your_huggingface_token

TWILIO_ACCOUNT_SID=your_twilio_account_sid

TWILIO_AUTH_TOKEN=your_twilio_auth_token

You can use .env.example as a reference.

Do not upload .env to GitHub.

5. Run the FastAPI Application

Start the application using Uvicorn:

uvicorn app.main:app --reload

The application will run locally at:

http://127.0.0.1:8000
6. Check the API

Open the following URL in your browser:

http://127.0.0.1:8000

To open the FastAPI Swagger documentation:

http://127.0.0.1:8000/docs

The /docs page can be used to test the available API endpoints.

7. Test the Agent Without a Phone Call

The agent can first be tested using the /process-speech endpoint.

Open another PowerShell terminal while the FastAPI server is running and execute:

Invoke-WebRequest `
  -Uri http://127.0.0.1:8000/process-speech `
  -Method POST `
  -Body @{
      SpeechResult="What does Naikroop do?"
      CallSid="RAGTEST123"
  }

The FastAPI terminal should show the user's question and the generated AI response.

Example:

============================================================
CALL SID: RAGTEST123
USER: What does Naikroop do?
============================================================

FINAL ANSWER:
Naikroop offers an enterprise-grade no-code platform...
8. Test Conversation Memory

Use the same CallSid to test follow-up questions.

First request:

Invoke-WebRequest `
  -Uri http://127.0.0.1:8000/process-speech `
  -Method POST `
  -Body @{
      SpeechResult="What does Naikroop do?"
      CallSid="RAGTEST123"
  }

Then send a follow-up question:

Invoke-WebRequest `
  -Uri http://127.0.0.1:8000/process-speech `
  -Method POST `
  -Body @{
      SpeechResult="Can you explain that more simply?"
      CallSid="RAGTEST123"
  }

Using the same CallSid allows the agent to use the previous conversation context.

9. Expose the Local Server Using TryCloudflare

Twilio needs a publicly accessible URL to communicate with the local FastAPI application.

Start the FastAPI server first:

uvicorn app.main:app --reload

Then open another terminal and start the Cloudflare tunnel:

cloudflared tunnel --url http://localhost:8000

Cloudflare will provide a public URL similar to:

https://example.trycloudflare.com

Copy the generated URL.

10. Configure Twilio

In the Twilio Console, configure the incoming voice webhook for your Twilio phone number.

Set the webhook URL to:

https://example.trycloudflare.com/voice

Set the HTTP method to:

POST

The URL should point to the /voice endpoint of the FastAPI application.

11. Make a Phone Call

Call your Twilio phone number.

The flow is:

User
  ↓
Phone Call
  ↓
Twilio
  ↓
/voice
  ↓
Speech Recognition
  ↓
/process-speech
  ↓
LangGraph Agent
  ↓
RAG + Short-Term Memory
  ↓
Hugging Face LLM
  ↓
AI Response
  ↓
Twilio Text-to-Speech
  ↓
User

You can then ask questions such as:

What does Naikroop do?

What is NaikFlow?

What services does Naikroop provide?

Can you explain that more simply?
12. RAG Knowledge Base

The Naikroop website is used as the knowledge source.

https://naikroop.com

The RAG pipeline performs:

Naikroop Website
       ↓
Website Crawling
       ↓
Text Extraction
       ↓
Text Chunking
       ↓
Embeddings
       ↓
FAISS Vector Store
       ↓
Relevant Knowledge
       ↓
Hugging Face LLM
       ↓
Final Answer

The generated FAISS vector store is stored locally in:

data/faiss_index/

This generated directory is excluded from Git using .gitignore.

13. Project Startup Summary

For normal development, use two terminals.

Terminal 1 — FastAPI
cd naikroop-ai-voice-agent
venv\Scripts\activate
uvicorn app.main:app --reload
Terminal 2 — TryCloudflare
cloudflared tunnel --url http://localhost:8000

Then configure the generated Cloudflare URL in Twilio:

https://YOUR-CLOUDFLARE-URL/voice

After that, call the Twilio number and interact with the AI voice agent.

