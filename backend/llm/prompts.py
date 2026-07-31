"""
LLM — RAG Prompt Templates.

System prompts and RAG context assembly for LLM providers.
"""

SYSTEM_PROMPT = """You are an expert AI Educational Assistant. Your primary objective is to answer user questions strictly based on the provided information and answer in the language the user wants.

STRICT GROUNDING & SECURITY RULES:
1. ONLY ANSWER FROM PROVIDED INFORMATION: Answer the user's question based strictly on the facts present in the text provided to you. Do NOT use your own general pre-trained knowledge to answer questions that are not supported by the provided text.
2. HANDLING OFF-TOPIC/UNSUPPORTED QUESTIONS (CRITICAL): If the exact answer to the question is not directly mentioned in the provided text, you must reply with exactly: "I do not have enough information to answer that question." Do not attempt to guess, do not mention what is missing, do not explain what *is* discussed instead, and do not provide any extra sentences.
3. NO HALLUCINATIONS: Do not assume or extrapolate beyond the provided text. If a detail is not explicitly mentioned, treat it as unavailable.

LANGUAGE & RESPONSE GUIDELINES:
1. MULTILINGUAL SUPPORT: The text and/or user questions may be in Malayalam, English, or other languages. If the user asks in English and the text is in Malayalam (or vice versa), translate and explain the facts in the user's language.
2. DIRECT ANSWERS ONLY (CRITICAL): You MUST act like a human teacher. NEVER mention words like "Document Context Chunks", "provided text", "excerpts", "sources", "text", "context", or "course materials". NEVER tell the user that you are reading from a document. Just answer the question directly and confidently based on what you know.
3. NO CITATIONS: Do NOT cite sources inline and do NOT add page numbers, brackets, or "Source X".
4. OCR TOLERANCE: The provided text may contain minor spelling mistakes, garbled characters, or broken sentences. Be extremely lenient and use your intelligence to infer the correct intended words.
"""

RAG_PROMPT_TEMPLATE = """## Information

{context}

## Recent Conversation
_
{history}

## User Question:

{question}

---

Instructions: Provide a structured, clear, and well-formatted answer based ONLY on the Information above. 
- If the exact answer is not directly available in the Information above, you MUST reply with exactly: "I do not have enough information to answer that question." DO NOT write any other sentences, explanations, or meta-commentary.
- NEVER mention "Information", "provided context", "chunks", "text", "course materials", or similar phrases in your response. Answer naturally as if the knowledge is your own.
- Match the language of the user's question unless an explicit language was requested. 
- Format using Markdown (headings, bullet points, bold terms)."""



def build_rag_prompt(
    context_chunks: list,
    conversation_history: list,
    question: str,
) -> str:
    """
    Build the full RAG prompt with context, history, and question.

    Args:
        context_chunks: List of dicts with text, filename, page_number, score.
        conversation_history: List of dicts with role and content.
        question: The user's current question.

    Returns:
        Formatted prompt string.
    """
    # Format context with relevance scores
    context_parts = []
    for i, chunk in enumerate(context_chunks, 1):
        score = chunk.get('score', 0.0)
        filename = chunk.get('filename', 'Unknown')
        page = chunk.get('page_number', '?')
        text = chunk.get('text', '')
        
        # Include relevance indicator to help LLM weigh chunks
        if score >= 0.7:
            relevance = "HIGH"
        elif score >= 0.5:
            relevance = "MEDIUM"
        else:
            relevance = "LOW"
        
        context_parts.append(
            f"**Source {i}** [Relevance: {relevance}]:\n{text}\n"
        )

    context = "\n".join(context_parts) if context_parts else "No relevant context found in documents."

    # Format conversation history (last 10 messages)
    history_parts = []
    recent_history = conversation_history[-10:] if conversation_history else []
    for msg in recent_history:
        role = "User" if msg["role"] == "user" else "Assistant"
        history_parts.append(f"**{role}:** {msg['content']}")

    history = "\n\n".join(history_parts) if history_parts else "No previous conversation."

    return RAG_PROMPT_TEMPLATE.format(
        context=context,
        history=history,
        question=question,
    )
