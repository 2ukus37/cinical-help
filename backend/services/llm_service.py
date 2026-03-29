"""
LLM-powered clinical narrative service via OpenRouter.
Uses stepfun/step-3.5-flash to generate human-readable clinical summaries
from structured SHAP explanations and prediction results.

The LLM is used ONLY for narrative generation — never for diagnosis.
All clinical decisions remain with the ML pipeline.
"""
import os
import json
import httpx
from dotenv import load_dotenv
from backend.utils.logger import model_logger

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "stepfun/step-3.5-flash")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
SYSTEM_PROMPT = """You are a friendly health AI assistant helping patients understand their health risk assessment results.
Your role is to explain ML prediction outputs in simple, caring language that a patient (not a doctor) can understand.

Rules:
- Use simple, everyday language — no medical jargon
- Be warm, supportive, and reassuring — never alarming
- Never say "diagnosis" — always say "risk assessment" or "health check result"
- Explain what the top factors mean in plain English (e.g. "your blood pressure reading" not "resting_bp")
- Always recommend consulting a doctor for next steps
- Keep it to 3-4 sentences
- End with: "Please share these results with your doctor for proper medical advice."
- Tone: warm, clear, supportive"""


def _build_prompt(
    disease: str,
    prediction: str,
    probability: float,
    risk_level: str,
    confidence_flag: str,
    top_factors: dict,
    interpretation: dict,
) -> str:
    factors_text = ", ".join(
        f"{feat} ({interp})"
        for feat, interp in list(interpretation.items())[:3]
    )
    return (
        f"Generate a friendly health summary for a patient based on their AI health check:\n\n"
        f"Health Check Type: {disease.replace('_', ' ').title()}\n"
        f"Result: {prediction}\n"
        f"Risk Level: {risk_level} ({probability:.1%} probability)\n"
        f"Confidence: {confidence_flag}\n"
        f"Key Factors: {factors_text}\n\n"
        f"Write a 3-sentence friendly explanation for the patient in simple language."
    )


def generate_clinical_narrative(
    disease: str,
    prediction: str,
    probability: float,
    risk_level: str,
    confidence_flag: str,
    explanation: dict,
) -> str:
    """
    Call OpenRouter LLM to generate a clinical narrative.
    Returns a plain-text narrative string.
    Falls back gracefully if the API is unavailable.
    """
    if not OPENROUTER_API_KEY:
        return _fallback_narrative(disease, prediction, probability, risk_level, explanation)

    top_factors = explanation.get("top_factors", {})
    interpretation = explanation.get("interpretation", {})

    if not top_factors:
        return _fallback_narrative(disease, prediction, probability, risk_level, explanation)

    prompt = _build_prompt(
        disease, prediction, probability, risk_level, confidence_flag,
        top_factors, interpretation,
    )

    try:
        with httpx.Client(timeout=20.0) as client:
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
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 512,   # enough for reasoning + response
                    "temperature": 0.3,
                },
            )
            response.raise_for_status()
            data = response.json()
            msg = data["choices"][0]["message"]

            # step-3.5-flash is a reasoning model: content may be null while
            # the answer is in reasoning. Extract the last sentence of reasoning
            # as the narrative if content is absent.
            narrative = msg.get("content") or ""
            if not narrative.strip():
                reasoning = msg.get("reasoning") or ""
                # Take the last coherent sentence from reasoning as the output
                sentences = [s.strip() for s in reasoning.replace("\n", " ").split(".") if len(s.strip()) > 20]
                narrative = ". ".join(sentences[-2:]) + "." if sentences else ""

            if not narrative.strip():
                raise ValueError("Empty response from LLM")

            model_logger.info(f"LLM narrative generated | model={OPENROUTER_MODEL}")
            return narrative.strip()

    except httpx.HTTPStatusError as e:
        model_logger.warning(f"LLM API HTTP error: {e.response.status_code} — using fallback")
        return _fallback_narrative(disease, prediction, probability, risk_level, explanation)
    except Exception as e:
        model_logger.warning(f"LLM API error: {e} — using fallback")
        return _fallback_narrative(disease, prediction, probability, risk_level, explanation)


def _fallback_narrative(
    disease: str,
    prediction: str,
    probability: float,
    risk_level: str,
    explanation: dict,
) -> str:
    """Rule-based fallback narrative when LLM is unavailable."""
    top = list(explanation.get("interpretation", {}).items())[:2]
    factors_str = " and ".join(f"{k} ({v})" for k, v in top) if top else "multiple clinical factors"
    return (
        f"The ML pipeline assessed this patient as {prediction.lower()} for "
        f"{disease.replace('_', ' ')} with a calibrated probability of {probability:.1%}, "
        f"corresponding to {risk_level}. "
        f"The primary contributing factors identified were {factors_str}. "
        f"This is a decision support output only. Clinical judgment is required."
    )
