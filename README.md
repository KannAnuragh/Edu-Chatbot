# 🎓 AI Course Assistant (Course-Based RAG Chatbot)

## Project Overview

**AI Course Assistant** is a production-oriented Retrieval-Augmented Generation (RAG) platform that enables students to have natural conversations with course materials. Administrators create courses and upload learning resources; the platform automatically processes these documents, builds a searchable knowledge base, and makes them available through an AI-powered conversational interface.

Students simply enroll in or select a course and interact with the course content through a ChatGPT-like interface. Every response is grounded in the uploaded documents and includes page-level citations for transparency and verification.

## Quick Start

```bash
# Clone and start
docker compose up --build -d

# Default accounts
# Admin:   admin@gmail.com / asdfasdf
# Student: student@example.com / password123
```

**Frontend**: http://localhost:3001  
**Backend API**: http://localhost:8001/docs  
**Qdrant Dashboard**: http://localhost:6335/dashboard

## Architecture

```
┌─────────────────────┐
│     Next.js UI      │
└──────────┬──────────┘
           │
    REST API / SSE
           │
┌──────────▼──────────┐
│      FastAPI        │
└───────┬─────┬───────┘
        │     │
PostgreSQL    Redis
        │     │
┌───────▼─────▼───────┐
│      Celery         │
└──────────┬──────────┘
           │
 Document Processing
           │
   Multilingual Embeddings
           │
       Qdrant Vector DB
           │
   Gemini LLM → Streaming Response
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, React, TypeScript, Tailwind CSS |
| Backend | FastAPI, Python, SQLAlchemy, Alembic |
| Auth | JWT, bcrypt, RBAC (Admin/Student) |
| LLM | Google Gemini (extensible to OpenAI/Groq) |
| Embeddings | sentence-transformers (multilingual) |
| Vector DB | Qdrant |
| Database | PostgreSQL 16 |
| Queue | Celery + Redis |
| Container | Docker Compose |

## Environment Variables

Copy `.env.example` files and configure:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

Key variable: `GEMINI_API_KEY` — required for LLM responses.
