import os
import hashlib
import json
import tempfile
import urllib.request
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import fitz

# Cache directory for font mappings
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "font_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# URL for a reliable open-source Malayalam font
REFERENCE_FONT_URL = "https://github.com/googlefonts/noto-fonts/raw/main/unhinted/ttf/NotoSansMalayalam/NotoSansMalayalam-Regular.ttf"
REFERENCE_FONT_PATH = os.path.join(CACHE_DIR, "NotoSansMalayalam-Regular.ttf")

def _download_reference_font():
    """Downloads the reference Malayalam font if it doesn't exist."""
    if not os.path.exists(REFERENCE_FONT_PATH):
        print("Downloading reference Noto Sans Malayalam font...")
        urllib.request.urlretrieve(REFERENCE_FONT_URL, REFERENCE_FONT_PATH)

def _render_char(char_str: str, font: ImageFont.FreeTypeFont, size=32) -> np.ndarray:
    """Renders a string to a normalized grayscale numpy array bitmap."""
    # Create a blank image with white background
    img = Image.new("L", (size * 2, size * 2), color=255)
    draw = ImageDraw.Draw(img)
    
    # Draw text in the center
    # Use textbbox to center the text
    try:
        bbox = draw.textbbox((0, 0), char_str, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = (size * 2 - w) / 2 - bbox[0]
        y = (size * 2 - h) / 2 - bbox[1]
        draw.text((x, y), char_str, font=font, fill=0)
    except Exception:
        pass # If rendering fails, return blank

    # Crop to the bounding box of the actual ink to make comparison invariant to positioning
    ink_box = img.getbbox()
    if ink_box:
        img = img.crop(ink_box)
    
    # Resize to standardized 32x32 for comparison
    img = img.resize((size, size), Image.Resampling.LANCZOS)
    return np.array(img)

def _build_reference_bitmaps() -> dict:
    """
    Builds a dictionary of {unicode_str: bitmap} for common Malayalam characters.
    """
    _download_reference_font()
    font = ImageFont.truetype(REFERENCE_FONT_PATH, 32)
    
    # Define common Malayalam target characters (Consonants, Vowels, Chillu, Conjuncts)
    # We include standalone matras, but we prepend a zero-width non-joiner or use them as is 
    # to avoid the dotted circle as much as possible, though some renderers force it.
    targets = [
        # Vowels
        "അ", "ആ", "ഇ", "ഈ", "ഉ", "ഊ", "ഋ", "എ", "ഏ", "ഐ", "ഒ", "ഓ", "ഔ", "അം", "അഃ",
        # Consonants
        "ക", "ഖ", "ഗ", "ഘ", "ങ", "ച", "ഛ", "ജ", "ഝ", "ഞ", "ട", "ഠ", "ഡ", "ഢ", "ണ",
        "ത", "ഥ", "ദ", "ധ", "ന", "പ", "ഫ", "ബ", "ഭ", "മ", "യ", "ര", "ല", "വ", "ശ",
        "ഷ", "സ", "ഹ", "ള", "ഴ", "റ",
        # Chillu
        "ൺ", "ൻ", "ർ", "ൽ", "ൾ", "ൿ",
        # Common Conjuncts
        "ക്ക", "ച്ച", "ട്ട", "ത്ത", "പ്പ", "ണ്ട", "ങ്ങ", "ഞ്ച", "ണ്ണ", "ന്ത", "മ്പ", "മ്പ", "ജ്ഞ", "ദ്ധ",
        "ങ്ക", "ങ്ങ", "സ്ഥ", "സ്ന", "സ്മ", "ക്ല", "പ്ല", "ഗ്ല", "ശ്ല",
        # Standalone Matras (Often mapped to single ASCII keys in legacy fonts)
        "ാ", "ി", "ീ", "ു", "ൂ", "ൃ", "െ", "േ", "ൈ", "ൊ", "ോ", "ൌ", "്"
    ]
    
    reference_bitmaps = {}
    for char in targets:
        reference_bitmaps[char] = _render_char(char, font)
        
    return reference_bitmaps

def _mse(imageA: np.ndarray, imageB: np.ndarray) -> float:
    """Compute the Mean Squared Error between two images."""
    err = np.sum((imageA.astype("float") - imageB.astype("float")) ** 2)
    err /= float(imageA.shape[0] * imageA.shape[1])
    return err

def get_dynamic_font_map(doc: fitz.Document, font_xref: int) -> dict:
    """
    Extracts a font from a PDF, visually compares its 8-bit glyphs against standard 
    Malayalam Unicode glyphs, and returns a generated character mapping dictionary.
    Caches the result by hashing the font file.
    """
    try:
        font_data = doc.extract_font(font_xref)
        if not font_data:
            return {}
            
        ext, font_buffer, _ = font_data
        
        # Hash the font buffer to use as cache key
        font_hash = hashlib.sha256(font_buffer).hexdigest()
        cache_file = os.path.join(CACHE_DIR, f"{font_hash}.json")
        
        if os.path.exists(cache_file):
            print(f"✅ [FontMapper] Found cached map for font {font_hash[:8]}")
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
                
        print(f"⚙️ [FontMapper] Generating dynamic map for font {font_hash[:8]}...")
        
        # Build references
        ref_bitmaps = _build_reference_bitmaps()
        
        # Save legacy font to temp file so Pillow can load it
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
            tmp.write(font_buffer)
            tmp_path = tmp.name
            
        try:
            legacy_font = ImageFont.truetype(tmp_path, 32)
            generated_map = {}
            
            # Legacy Indic fonts map Malayalam glyphs to standard 8-bit character codes (32-255)
            for i in range(32, 256):
                char = chr(i)
                legacy_bitmap = _render_char(char, legacy_font)
                
                # Find best match
                best_match = None
                best_score = float('inf')
                
                # Only map if it's not empty/blank space
                if np.mean(legacy_bitmap) < 254:
                    for ref_char, ref_bitmap in ref_bitmaps.items():
                        score = _mse(legacy_bitmap, ref_bitmap)
                        if score < best_score:
                            best_score = score
                            best_match = ref_char
                            
                    # Threshold: only accept reasonably close visual matches
                    if best_match and best_score < 5000:
                        generated_map[char] = best_match
                        
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                
        # Save to cache
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(generated_map, f, ensure_ascii=False, indent=2)
            
        print(f"✅ [FontMapper] Generated and cached {len(generated_map)} mappings.")
        return generated_map
        
    except Exception as e:
        print(f"⚠️ [FontMapper] Error generating map: {e}")
        return {}
