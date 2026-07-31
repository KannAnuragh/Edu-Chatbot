"""
LLM — RAG Prompt Templates.

System prompts and RAG context assembly for LLM providers.
"""

SYSTEM_PROMPT = """You are an expert AI Educational Assistant. Your primary objective is to answer user questions strictly based on the provided information.

STRICT GROUNDING RULES:
1. If the provided information contains the answer to the user's question, answer the question directly, accurately, and concisely using only those facts. Do not add any meta-commentary, do not explain which sources you used, and do not mention the words "context", "text", or "chunks".
2. If the provided information does not contain the answer to the question, you must respond with exactly this single sentence and nothing else:
"I do not have enough information to answer that question."
Do not attempt to answer partially, do not guess, and do not write any other text.
"""

RAG_PROMPT_TEMPLATE = """## Information

{context}

## Recent Conversation
_
{history}

## User Question:

{question}

---

Instructions:
- If the answer is present in the Information above, provide a direct and structured answer.
- If the answer is NOT present in the Information above, reply ONLY with: "I do not have enough information to answer that question."
- Never mention "Information", "context", "chunks", or "documents" in your response.
- Match the language of the user's question."""



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
