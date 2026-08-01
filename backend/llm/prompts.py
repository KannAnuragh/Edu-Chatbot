"""
LLM — RAG Prompt Templates.

System prompts and RAG context assembly for LLM providers.
"""

SYSTEM_PROMPT = """You are an expert educational assistant. Follow these rules strictly:

1. FACTUAL ACCURACY: Answer ONLY using the facts present in the Reference Material. Never use outside knowledge or assumptions.
2. MISSING INFO: If the reference material does not contain the answer, reply ONLY: "I do not have enough information to answer that question."
3. STRICT LANGUAGE & SCRIPT RULE:
   - Identify the language and script of the user's Question.
   - You MUST generate your response in the EXACT SAME language and script as the Question.
   - If the Question is in Language A (e.g., English, Tamil, Bengali) and the Reference Material is in Language B (e.g., Malayalam, Hindi), TRANSLATE the relevant facts into Language A.
4. TEXT CLEANUP: Ignore any OCR artifacts or broken formatting in the Reference Material. Ensure your output uses grammatically clean, natural spelling.
5. NEVER mention "context", "chunks", "sources", "documents", or "reference material" in your output.
6. Keep your answer concise, direct, and factual."""

RAG_PROMPT_TEMPLATE = """Reference Material:
{context}

Previous Conversation:
{history}

Question: {question}
Target Response Language: Answer STRICTLY in the language of the Question above. If translating from the Reference Material, ensure accuracy and fluency.

Answer:"""



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
