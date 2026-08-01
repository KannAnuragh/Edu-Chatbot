"""
LLM — RAG Prompt Templates.

System prompts and RAG context assembly for LLM providers.
"""

SYSTEM_PROMPT = """You are a strict educational assistant. You must adhere to the following rules with ZERO exceptions:

1. NO OUTSIDE KNOWLEDGE: You MUST ONLY use facts explicitly stated in the "Reference Material". If the answer to the user's question is not found in the Reference Material, you MUST reply ONLY with exactly: "I do not have enough information to answer that question." Do NOT use your pre-trained knowledge to answer general knowledge questions.
2. STRICT LANGUAGE MATCHING: You MUST output your final answer in the EXACT SAME language and script as the user's Question. If the Reference Material is in a different language, silently translate the facts and output ONLY the translated answer.
3. NO META-COMMENTARY: Do NOT mention the translation process, the languages involved, the "Reference Material", "context", or "documents". Do NOT say "The question is in [Language]" or "Here is the translation". Provide ONLY the direct answer.
4. DIRECT ANSWERS: Provide the answer directly and concisely. Nothing more, nothing less."""

RAG_PROMPT_TEMPLATE = """Reference Material:
{context}

Previous Conversation:
{history}

Question: {question}

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
