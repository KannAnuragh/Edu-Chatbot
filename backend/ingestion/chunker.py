"""
Text Chunker.

Splits document text into manageable chunks while preserving context.
"""

import re
from dataclasses import dataclass
from typing import List, Dict, Any

from core.config import settings

@dataclass
class ChunkData:
    text: str
    page_number: int


def chunk_text(pages_text: List[tuple[int, str]], filename: str) -> List[Dict[str, Any]]:
    """
    Chunk text recursively based on character limits.
    Prepends context (filename and page number) to each chunk.
    """
    chunks = []
    
    for page_num, text in pages_text:
        # Recursive splitting strategy: Paragraphs -> Sentences -> Words -> Characters
        page_chunks = _recursive_split(
            text, 
            chunk_size=settings.CHUNK_SIZE, 
            overlap=settings.CHUNK_OVERLAP
        )
        
        for chunk_text in page_chunks:
            if not chunk_text.strip():
                continue
                
            # Prepend context to the chunk to help the LLM and Embedding model
            context_header = f"File: {filename}, Page: {page_num}\n---\n"
            full_chunk = context_header + chunk_text
            
            chunks.append({
                "text": full_chunk,
                "page_number": page_num
            })
            
    return chunks


def _recursive_split(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Recursively split text trying natural boundaries first."""
    
    if len(text) <= chunk_size:
        return [text]
        
    # Try separating by double newlines, single newlines, then spaces
    separators = [r'\n\s*\n', r'\n', r'(?<=[.!?])\s+', r'\s+']
    
    for sep_regex in separators:
        pieces = re.split(sep_regex, text)
        if len(pieces) > 1:
            # We found a valid separator that splits the text
            # Depending on regex, re.split might leave empty strings if there are trailing separators.
            pieces = [p for p in pieces if p]
            
            # If after filtering it didn't actually split, try next separator
            if len(pieces) <= 1:
                continue
                
            return _apply_overlap(pieces, chunk_size, overlap, " ")

    # Fallback: strict character splitting (guarantees chunk_size limit)
    step = max(1, chunk_size - overlap)
    return [text[i:i + chunk_size] for i in range(0, len(text), step)]


def _apply_overlap(pieces: List[str], max_size: int, overlap: int, separator: str) -> List[str]:
    """Combine pieces until max_size, sliding window by overlap. Strictly enforces max_size."""
    chunks = []
    current_chunk = ""
    
    for piece in pieces:
        if not piece:
            continue
            
        # If a single piece is larger than max_size, it MUST be recursively split
        # otherwise we'll break the token limit of the embedding model.
        if len(piece) > max_size:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            # Force split this oversized piece
            sub_chunks = _recursive_split(piece, max_size, overlap)
            chunks.extend(sub_chunks)
            continue
            
        proposed = current_chunk + (separator if current_chunk else "") + piece
        
        if len(proposed) <= max_size:
            current_chunk = proposed
        else:
            if current_chunk:
                chunks.append(current_chunk)
                
            # Start new chunk with overlap
            if len(current_chunk) > overlap:
                overlap_text = current_chunk[-overlap:]
                first_space = overlap_text.find(' ')
                if first_space != -1 and first_space < len(overlap_text) - 10:
                    overlap_text = overlap_text[first_space+1:]
                current_chunk = overlap_text + separator + piece
            else:
                current_chunk = piece
                
    if current_chunk:
        chunks.append(current_chunk)
        
    return chunks
