"""
LLM — RAG Prompt Templates.

System prompts and RAG context assembly for Gemini.
"""

SYSTEM_PROMPT = """You are a helpful AI assistant that answers questions about PDF documents using the provided context chunks.

GUIDELINES:
1. ALWAYS read and analyze the provided Document Context Chunks carefully. Extract facts, ideas, and details to answer the user's question directly.
2. MULTILINGUAL SUPPORT: The document context and/or user questions may be in Malayalam, English, or other languages. Understand text written in any language/script (such as Malayalam). If the user asks in English and the chunks are in Malayalam (or vice versa), translate and explain the facts in the user's language.
3. CONTEXT SYNTHESIS: Synthesize information from all retrieved chunks. Do NOT refuse to answer or output refusal messages when relevant context chunks are provided. Always construct a helpful response from the retrieved text.
4. DIRECT ANSWERS ONLY: DO NOT start your response with filler phrases like "Based on the provided documents," or "Here is the information from the text." Just answer the question directly and naturally.
5. NO CITATIONS: Do NOT cite sources inline and do NOT add page numbers or brackets. Just provide the plain text answer.
"""

RAG_PROMPT_TEMPLATE = """## Document Context Chunks

{context}

## Recent Conversation

{history}

## User Question

{question}

---

Provide a clear, detailed, and helpful answer to the user's question based on the Document Context Chunks above. Do NOT use introductory filler phrases and do NOT cite sources."""


def build_rag_prompt(
    context_chunks: list,
    conversation_history: list,
    question: str,
) -> str:
    """
    Build the full RAG prompt with context, history, and question.

    Args:
        context_chunks: List of dicts with text, filename, page_number.
        conversation_history: List of dicts with role and content.
        question: The user's current question.

    Returns:
        Formatted prompt string.
    """
    # Format context
    context_parts = []
    for i, chunk in enumerate(context_chunks, 1):
        context_parts.append(f"**Source {i}**:\n{chunk['text']}\n")

    context = "\n".join(context_parts) if context_parts else "No relevant context found."

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
