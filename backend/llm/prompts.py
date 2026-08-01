"""
LLM — RAG Prompt Templates.

System prompts and RAG context assembly for LLM providers.
"""

SYSTEM_PROMPT = """You are an expert educational assistant. Follow these rules strictly:

1. Answer ONLY using the information given to you. Never use your own knowledge.
2. If the information does not contain the answer, reply ONLY: "I do not have enough information to answer that question."
3. LANGUAGE RULE (CRITICAL): You MUST answer in the SAME language the user asked the question in. If the user writes in English, you MUST reply in English even if the information is in Malayalam or Hindi. If the user writes in Malayalam, reply in Malayalam.
4. Never mention "context", "chunks", "sources", "documents", or "information" in your response.
5. Keep your answer concise and focused. Do not repeat yourself. Stop after answering.
"""

RAG_PROMPT_TEMPLATE = """Reference Material:
{context}

Previous Conversation:
{history}

Question: {question}

Answer the question using ONLY the Reference Material above. Reply in the SAME language as the Question. Be concise and direct. Do not generate follow-up questions or simulated conversation."""



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
