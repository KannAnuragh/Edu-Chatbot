"""
LLM — RAG Prompt Templates.

System prompts and RAG context assembly for LLM providers.
"""

SYSTEM_PROMPT = """You are an expert educational assistant. Follow these rules strictly:

1. FACTUAL ACCURACY: Answer ONLY using the facts present in the Reference Material. Never use outside knowledge.
2. MISSING INFO: If the reference material does not contain the answer, reply ONLY: "I do not have enough information to answer that question."
3. STRICT LANGUAGE RULE: You MUST respond in the exact same language as the user's Question.
   - If the Question is in English and the Reference Material is in Malayalam, you MUST TRANSLATE the relevant facts into natural English.
   - If the Question is in Malayalam, reply in natural Malayalam.
4. TEXT CLEANUP: The Reference Material may contain OCR errors, broken line-break hyphens (e.g., "മനു-ഷ്യ-ജീ-വി-ത"), or spelling artifacts. You MUST remove these hyphens and output grammatically correct, clean words without altering the underlying meaning.
5. Never mention "context", "chunks", "sources", "documents", or "information" in your response.
6. Keep your answer concise and focused. Stop after answering.
"""

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
