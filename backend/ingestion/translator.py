"""
Offline Malayalam to English Translator.

Uses MarianMT (Helsinki-NLP/opus-mt-ml-en) to translate text locally.
Lazy-loaded to save RAM.
"""

from typing import List
import time

_model = None
_tokenizer = None

def _load_model():
    """Lazy load the translation model."""
    global _model, _tokenizer
    if _model is None or _tokenizer is None:
        print("⏳ [Translator] Loading Helsinki-NLP/opus-mt-ml-en model offline...")
        t0 = time.time()
        
        # We import here so transformers/torch are only loaded if translation is actually needed
        from transformers import MarianMTModel, MarianTokenizer
        import torch
        
        model_name = "Helsinki-NLP/opus-mt-ml-en"
        
        # Use CPU, it's fast enough for document chunks and saves VRAM
        device = "cpu"
        
        _tokenizer = MarianTokenizer.from_pretrained(model_name)
        _model = MarianMTModel.from_pretrained(model_name).to(device)
        
        t1 = time.time()
        print(f"✅ [Translator] Model loaded in {t1 - t0:.2f} seconds.")

def translate_chunks(texts: List[str], batch_size: int = 4) -> List[str]:
    """
    Translate a list of Malayalam text chunks into English.
    
    Args:
        texts: List of Malayalam text chunks
        batch_size: Number of chunks to translate simultaneously
        
    Returns:
        List of translated English chunks
    """
    if not texts:
        return []
        
    _load_model()
    import torch
    
    translated_texts = []
    
    print(f"🔄 [Translator] Translating {len(texts)} chunks from Malayalam to English...")
    t0 = time.time()
    
    # Process in batches to avoid OOM or sequence length errors
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        
        # Tokenize (MarianMT has a max length, usually 512)
        encoded = _tokenizer(batch, return_tensors="pt", padding=True, truncation=True, max_length=512)
        
        with torch.no_grad():
            generated_tokens = _model.generate(**encoded)
            
        decoded = _tokenizer.batch_decode(generated_tokens, skip_special_tokens=True)
        translated_texts.extend(decoded)
        
    t1 = time.time()
    print(f"✅ [Translator] Translation completed in {t1 - t0:.2f} seconds.")
    
    return translated_texts
