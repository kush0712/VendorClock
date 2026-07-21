"""
LLM Extraction Service — Invoice OCR field extraction

Routing strategy per spec:
  PRIMARY:  Groq (Llama/Qwen) — no training on submitted data. Safe for real PAN/GSTIN.
  FALLBACK: Gemini — ⚠ free tier TRAINS on submitted prompts by default.
            Only used for non-sensitive/test traffic.
            NEVER send real vendor PAN, GSTIN, amounts, or names to Gemini.

Phase 2: add Ollama local model as a third option for fully air-gapped environments.
"""

import json
import re
from typing import Optional
from datetime import datetime

from app.core.config import settings


def _clean_json(text: str) -> str:
    """Extract JSON from LLM response that may have markdown fences."""
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        return match.group(1).strip()
    return text.strip()


EXTRACTION_PROMPT = """
You are a financial document parser. Extract the following fields from the invoice text below.
Return a single valid JSON object with exactly these keys:
{
  "invoice_number": string or null,
  "invoice_date": "YYYY-MM-DD" or null,
  "vendor_name": string or null,
  "vendor_gstin": string or null,
  "delivery_date": "YYYY-MM-DD" or null,
  "total_amount": number or null,
  "gst_amount": number or null,
  "currency": "INR" or other or null
}

Rules:
- Dates must be in YYYY-MM-DD format.
- Amounts must be numbers (no currency symbols or commas).
- If a field is not present, use null.
- Return ONLY the JSON object, no explanation.

Invoice text:
"""


async def extract_with_groq(raw_text: str) -> Optional[dict]:
    """
    Extract structured invoice fields using Groq API (PRIMARY — safe for real data).
    """
    if not settings.GROQ_API_KEY:
        return None
    try:
        from groq import Groq
        client = Groq(api_key=settings.GROQ_API_KEY)
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "user", "content": EXTRACTION_PROMPT + raw_text[:3000]},
            ],
            temperature=0.1,
            max_tokens=512,
        )
        raw = response.choices[0].message.content or ""
        return json.loads(_clean_json(raw))
    except Exception as e:
        print(f"[LLM] Groq extraction failed: {e}")
        return None


async def extract_with_gemini(raw_text: str, is_sensitive: bool = True) -> Optional[dict]:
    """
    Extract structured invoice fields using Gemini (FALLBACK — NON-SENSITIVE ONLY).

    ⚠ CRITICAL: Gemini free tier trains on submitted prompts by default.
    DO NOT call this with real vendor PAN, GSTIN, amounts, or business names.
    Only use for test/synthetic data or when is_sensitive=False.
    """
    if is_sensitive:
        raise ValueError(
            "SECURITY VIOLATION: Attempted to send sensitive invoice data to Gemini free tier. "
            "Gemini trains on submitted prompts — real PAN/GSTIN data must never go here. "
            "Use Groq (primary) instead."
        )
    if not settings.GEMINI_API_KEY:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(settings.GEMINI_MODEL)
        response = model.generate_content(EXTRACTION_PROMPT + raw_text[:3000])
        raw = response.text or ""
        return json.loads(_clean_json(raw))
    except Exception as e:
        print(f"[LLM] Gemini extraction failed: {e}")
        return None


async def extract_invoice_fields(raw_text: str, is_real_data: bool = True) -> Optional[dict]:
    """
    Route to the appropriate LLM based on data sensitivity.

    is_real_data=True  → Groq only (safe, no training)
    is_real_data=False → Groq first, Gemini fallback (test traffic only)
    """
    # Always try Groq first
    result = await extract_with_groq(raw_text)
    if result:
        return result

    # Fallback to Gemini ONLY for non-sensitive data
    if not is_real_data:
        return await extract_with_gemini(raw_text, is_sensitive=False)

    # If Groq failed and data is sensitive — return None, trigger manual correction UI
    print("[LLM] Groq failed and data is sensitive — skipping Gemini, returning None for manual correction.")
    return None
