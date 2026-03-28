"""
Document parsing service for CDSS.
Accepts CT scan reports, lab reports, ECG reports, and medical PDFs/images.
Uses the LLM (stepfun/step-3.5-flash) to extract clinical values from text.
"""
import os
import io
import re
import base64
import httpx
from pathlib import Path
from dotenv import load_dotenv
from backend.utils.logger import model_logger

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "stepfun/step-3.5-flash")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

UPLOAD_DIR = Path("backend/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_TYPES = {
    "application/pdf", "image/jpeg", "image/png",
    "image/jpg", "image/webp", "image/tiff",
}

EXTRACT_PROMPT = """Extract clinical values from this medical document. Output ONLY a JSON object, nothing else.

JSON format (use null for missing values):
{"age":null,"sex":null,"resting_bp":null,"cholesterol":null,"max_heart_rate":null,"fasting_blood_sugar":null,"resting_ecg":null,"chest_pain_type":null,"exercise_angina":null,"st_depression":null,"st_slope":null,"num_vessels":null,"thal":null,"glucose":null,"blood_pressure":null,"bmi":null,"insulin":null,"skin_thickness":null,"pregnancies":null,"diabetes_pedigree":null,"document_summary":"brief description"}

Rules: age=integer, sex=1(male)/0(female), resting_bp=systolic mmHg, fasting_blood_sugar=1 if glucose>120 else 0.
Output the JSON object immediately with no explanation."""


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract all text from a PDF file."""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            text = "\n".join(
                page.extract_text() or "" for page in pdf.pages
            )
        return text.strip()
    except Exception as e:
        model_logger.warning(f"PDF text extraction failed: {e}")
        return ""


def extract_text_from_image(file_bytes: bytes) -> str:
    """Convert image to base64 for LLM vision processing."""
    # Return base64 — we'll send it directly to the LLM
    return base64.b64encode(file_bytes).decode("utf-8")


def parse_document_with_llm(text: str = "", image_b64: str = "", filename: str = "") -> dict:
    """
    Send document content to LLM for clinical value extraction.
    Supports both text (PDF) and image (CT scan, lab report photo) inputs.
    """
    if not OPENROUTER_API_KEY:
        return {"error": "LLM API not configured", "document_summary": "API key missing"}

    messages = []

    if image_b64:
        # Vision: send image directly
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": EXTRACT_PROMPT},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{image_b64}"
                }}
            ]
        }]
    elif text:
        # Text: send extracted PDF text
        messages = [{
            "role": "user",
            "content": f"{EXTRACT_PROMPT}\n\nDocument content:\n{text[:4000]}"
        }]
    else:
        return {"error": "No content to parse", "document_summary": "Empty document"}

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://cdss.clinical-obsidian.ai",
                    "X-Title": "Clinical Obsidian CDSS",
                },
                json={
                    "model": OPENROUTER_MODEL,
                    "messages": messages,
                    "max_tokens": 1024,
                    "temperature": 0.1,
                },
            )
            response.raise_for_status()
            data = response.json()
            msg = data["choices"][0]["message"]
            content = msg.get("content") or ""
            reasoning = msg.get("reasoning") or ""
            # Search content first, then reasoning (step-3.5-flash is a reasoning model)
            full_text = content + "\n" + reasoning

            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*?\}(?=\s*$|\s*\n)', full_text)
            if not json_match:
                json_match = re.search(r'\{[\s\S]*\}', full_text)
            if json_match:
                import json as _json
                try:
                    parsed = _json.loads(json_match.group())
                    cleaned = {k: v for k, v in parsed.items() if v is not None}
                    model_logger.info(f"Document parsed: {len(cleaned)} fields extracted from {filename}")
                    return cleaned
                except _json.JSONDecodeError:
                    pass
            return {"error": "Could not parse JSON from LLM response", "document_summary": "Parse failed", "raw": full_text[:200]}

    except Exception as e:
        model_logger.warning(f"Document LLM parse error: {e}")
        return {"error": str(e), "document_summary": "Extraction failed"}


def _regex_fallback(text: str) -> dict:
    """Extract common clinical values from text using regex when LLM fails."""
    import re as _re
    result = {}
    patterns = {
        'age':           r'\bage[:\s]+(\d{1,3})',
        'resting_bp':    r'(?:blood pressure|bp)[:\s]+(\d{2,3})\s*/\s*\d+',
        'cholesterol':   r'(?:cholesterol|chol)[:\s]+(\d{2,3})',
        'max_heart_rate':r'(?:max(?:imum)? heart rate|max hr|heart rate)[:\s]+(\d{2,3})',
        'glucose':       r'(?:glucose|blood sugar|fasting glucose)[:\s]+(\d{2,3})',
        'bmi':           r'bmi[:\s]+(\d{1,2}\.?\d*)',
        'insulin':       r'insulin[:\s]+(\d{1,4})',
        'blood_pressure':r'(?:diastolic|blood pressure)[:\s]+\d+\s*/\s*(\d{2,3})',
    }
    t = text.lower()
    for field, pat in patterns.items():
        m = _re.search(pat, t)
        if m:
            try: result[field] = float(m.group(1)) if '.' in m.group(1) else int(m.group(1))
            except: pass
    # Sex
    if 'male' in t and 'female' not in t: result['sex'] = 1
    elif 'female' in t: result['sex'] = 0
    # Fasting blood sugar flag
    if 'glucose' in result and result['glucose'] > 120:
        result['fasting_blood_sugar'] = 1
    if result:
        result['document_summary'] = 'Values extracted from medical document (regex)'
    return result
    """
    Main entry point: validate, extract text/image, parse with LLM.
    Returns extracted clinical fields ready for the prediction form.
    """
    # Validate file type
    if content_type not in ALLOWED_TYPES:
        raise ValueError(f"Unsupported file type: {content_type}. Allowed: PDF, JPG, PNG, WEBP")

    # Validate file size (max 10MB)
    if len(file_bytes) > 10 * 1024 * 1024:
        raise ValueError("File too large. Maximum size is 10MB.")

    model_logger.info(f"Processing upload: {filename} ({content_type}, {len(file_bytes)} bytes)")

    if content_type == "application/pdf":
        text = extract_text_from_pdf(file_bytes)
        if not text:
            return {"error": "Could not extract text from PDF. Try uploading an image instead.", "document_summary": "Empty PDF"}
        result = parse_document_with_llm(text=text, filename=filename)
        # If LLM only returned summary, try regex fallback on the text
        if len([k for k in result if k != 'document_summary' and k != 'error']) == 0:
            fallback = _regex_fallback(text)
            if fallback:
                return fallback
        return result
    else:
        image_b64 = extract_text_from_image(file_bytes)
        return parse_document_with_llm(image_b64=image_b64, filename=filename)
