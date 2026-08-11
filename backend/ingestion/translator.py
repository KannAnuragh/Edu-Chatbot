"""
Pass-through Translator module.
Document translation during ingestion has been disabled in favor of offline
Unicode normalization, layout-aware extraction, and prompt-level translation.
"""

from typing import List

def translate_chunks(texts: List[str]) -> List[str]:
    """Pass-through function returning original texts."""
    return texts
