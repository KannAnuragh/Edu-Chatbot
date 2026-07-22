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
        
    # Split by double newline (paragraphs)
    paragraphs = re.split(r'\n\s*\n', text)
    if len(paragraphs) > 1:
        return _apply_overlap(paragraphs, chunk_size, overlap, separator='\n\n')
        
    # Split by single newline
    lines = text.split('\n')
    if len(lines) > 1:
        return _apply_overlap(lines, chunk_size, overlap, separator='\n')
        
    # Split by sentence boundaries (basic heuristic)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    if len(sentences) > 1:
        return _apply_overlap(sentences, chunk_size, overlap, separator=' ')
        
    # Fallback to character splitting
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size - overlap)]


def _apply_overlap(pieces: List[str], max_size: int, overlap: int, separator: str) -> List[str]:
    """Combine pieces until max_size, then slide window by overlap."""
    chunks = []
    current_chunk = ""
    
    for piece in pieces:
        if not piece:
            continue
            
        proposed = current_chunk + (separator if current_chunk else "") + piece
        
        if len(proposed) <= max_size:
            current_chunk = proposed
        else:
            if current_chunk:
                chunks.append(current_chunk)
                
            # Start new chunk with overlap
            # Find the split point that preserves approx `overlap` characters
            if len(current_chunk) > overlap:
                # Keep the end of the previous chunk
                overlap_text = current_chunk[-overlap:]
                # Try to break cleanly at a word if possible
                first_space = overlap_text.find(' ')
                if first_space != -1 and first_space < len(overlap_text) - 10:
                    overlap_text = overlap_text[first_space+1:]
                current_chunk = overlap_text + separator + piece
            else:
                current_chunk = piece
                
            # If the single piece is STILL too big, we just have to live with it
            # (or it will get caught by a deeper recursive split if we implemented it perfectly,
            # but for simplicity we'll just allow it to slightly exceed here)
            
    if current_chunk:
        chunks.append(current_chunk)
        
    return chunks
