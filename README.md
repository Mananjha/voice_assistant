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
