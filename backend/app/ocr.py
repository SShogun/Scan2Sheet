import os
import shutil
from PIL import Image, ImageOps, UnidentifiedImageError
from fastapi import HTTPException
import pytesseract
import io

OCR_TIMEOUT_SECONDS = 8
OCR_MAX_DIMENSION = 1800

def _configure_tesseract() -> None:
    if shutil.which("tesseract"):
        return

    possible_paths = [
        r"C:\\Users\\soham\\AppData\\Local\\Tesseract-OCR\\tesseract.exe",
        r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
        r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
    ]
    for path in possible_paths:
        if os.path.exists(path):
            try:
                pytesseract.pytesseract.tesseract_cmd = path
                break
            except Exception:
                continue

def _decode_image(image_bytes: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image.load()
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Unsupported or corrupt image file.") from exc
    return image

def _preprocess_image(image: Image.Image) -> Image.Image:
    # 1. Handle transparency (Alpha channel)
    # If a PNG has a transparent background, converting directly to grayscale makes it black, destroying text!
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        bg = Image.new("RGB", image.size, (255, 255, 255))
        bg.paste(image, mask=image.convert("RGBA").split()[3])
        image = bg
    else:
        image = image.convert("RGB")
        
    # 2. Convert to grayscale
    grayscale = ImageOps.grayscale(image)
    
    # 3. Scale appropriately for Tesseract (needs ~300 DPI, so large pixel dimensions)
    max_dim = max(grayscale.width, grayscale.height)
    if max_dim < 2500:
        scale_factor = 2500.0 / max_dim
        new_w = int(grayscale.width * scale_factor)
        new_h = int(grayscale.height * scale_factor)
        grayscale = grayscale.resize((new_w, new_h), Image.Resampling.LANCZOS)
    elif max_dim > 4000:
        grayscale.thumbnail((4000, 4000), Image.Resampling.LANCZOS)
        
    return grayscale

def _ocr_image(image: Image.Image) -> tuple[str, float]:
    _configure_tesseract()
    try:
        raw_text = pytesseract.image_to_string(
            image,
            config="--oem 1 --psm 3",
            timeout=15,
        ).strip()
    except pytesseract.TesseractError as exc:
        raise HTTPException(status_code=500, detail=f"OCR failed: {exc}") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=504, detail="OCR timed out. Use a smaller or cleaner image.") from exc

    text_length_score = min(100.0, max(0.0, len(raw_text) * 2.5))
    return raw_text, text_length_score

