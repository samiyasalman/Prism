"""Cross-Border Financial Document Analyzer — FastAPI router.

Endpoints:
  POST /agent/upload   — accepts files, stores locally, returns file_ids
  POST /agent/analyze  — extracts text from files, sends to IBM watsonx
                         Orchestrate agent, returns structured analysis
"""

import json
import os
import re
import time
import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.config import settings
from app.models import User

router = APIRouter(prefix="/agent", tags=["financial-agent"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "agent_uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per file

# ── Token cache ──────────────────────────────────────────────────────
_mcsp_token: str = ""
_mcsp_token_expiry: float = 0


async def _get_mcsp_token() -> str:
    """Get or refresh the MCSP bearer token for watsonx Orchestrate."""
    global _mcsp_token, _mcsp_token_expiry

    if _mcsp_token and time.time() < _mcsp_token_expiry - 60:
        return _mcsp_token

    if not settings.wxo_mcsp_apikey:
        raise HTTPException(status_code=500, detail="WXO_MCSP_APIKEY not configured")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://iam.platform.saas.ibm.com/siusermgr/api/1.0/apikeys/token",
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            json={"apikey": settings.wxo_mcsp_apikey},
        )
        resp.raise_for_status()
        data = resp.json()

    _mcsp_token = data["token"]
    _mcsp_token_expiry = time.time() + data.get("expires_in", 7200)
    return _mcsp_token


# ── Text extraction helpers ──────────────────────────────────────────

def _extract_text_from_pdf(file_path: Path) -> str:
    from PyPDF2 import PdfReader
    reader = PdfReader(str(file_path))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)
    return "\n\n".join(pages)


def _extract_text_from_image(file_path: Path) -> str:
    from PIL import Image
    import pytesseract
    img = Image.open(str(file_path))
    return pytesseract.image_to_string(img)


def _extract_text(file_path: Path) -> str:
    """Extract text from a file based on its extension."""
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        return _extract_text_from_pdf(file_path)
    elif ext in (".png", ".jpg", ".jpeg", ".tiff"):
        return _extract_text_from_image(file_path)
    elif ext in (".txt", ".csv"):
        return file_path.read_text(errors="replace")
    else:
        return file_path.read_text(errors="replace")


# ── Orchestrate agent call ───────────────────────────────────────────

async def _call_orchestrate_agent(
    extracted_text: str,
    target_language: str,
    target_currency: str,
    num_files: int,
) -> dict:
    """Send extracted text to the watsonx Orchestrate agent and parse response."""
    token = await _get_mcsp_token()

    lang_map = {"en": "English", "fr": "French", "es": "Spanish", "de": "German"}
    lang_label = lang_map.get(target_language, target_language)

    prompt = (
        f"Please analyze the following financial document content. "
        f"Language: {lang_label}. Currency: {target_currency}.\n\n"
        f"--- DOCUMENT CONTENT ---\n{extracted_text[:15000]}\n--- END ---\n\n"
        f"Return the structured JSON analysis."
    )

    instance_url = settings.wxo_instance_url.rstrip("/")
    agent_id = settings.wxo_agent_id

    # Use non-streaming runs endpoint and poll for result
    async with httpx.AsyncClient(timeout=120) as client:
        # Start the run
        resp = await client.post(
            f"{instance_url}/v1/orchestrate/runs",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "message": {"role": "user", "content": prompt},
                "agent_id": agent_id,
            },
        )
        resp.raise_for_status()
        run_data = resp.json()
        thread_id = run_data["thread_id"]

        # Poll for completion (up to 90 seconds)
        for _ in range(30):
            await _async_sleep(3)
            msgs_resp = await client.get(
                f"{instance_url}/v1/orchestrate/threads/{thread_id}/messages",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
            )
            msgs_resp.raise_for_status()
            messages = msgs_resp.json()

            # Find the assistant's response
            assistant_msgs = [m for m in messages if m["role"] == "assistant"]
            if assistant_msgs:
                last_msg = assistant_msgs[-1]
                content_parts = last_msg.get("content", [])
                full_text = "".join(p.get("text", "") for p in content_parts)
                return _parse_agent_response(full_text, target_currency, num_files)

    raise HTTPException(status_code=504, detail="Agent did not respond in time")


async def _async_sleep(seconds: float):
    import asyncio
    await asyncio.sleep(seconds)


def _parse_agent_response(text: str, currency: str, num_files: int) -> dict:
    """Parse the agent's response text into the expected frontend format."""
    # Try to extract JSON from the response
    json_obj = None

    # Try direct JSON parse
    try:
        json_obj = json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON block in markdown code fence
    if not json_obj:
        match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
        if match:
            try:
                json_obj = json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

    # Try to find any JSON object in the text
    if not json_obj:
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                json_obj = json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

    if not json_obj:
        # Return a text-only response if no JSON found
        return {
            "summary": {
                "text": text[:2000],
                "country_context": "",
                "currency_context": f"Target currency: {currency}",
            },
            "financial_signals": {
                "monthly_income": None,
                "annual_income": None,
                "outstanding_loan_balances": None,
                "credit_card_balances": None,
                "recurring_obligations": None,
            },
            "missing_signals": ["Could not parse structured response"],
            "processing_metadata": {
                "date_processed": _now_iso(),
                "tools_used": ["watsonx Orchestrate"],
                "notes": "Agent returned text but no parseable JSON.",
            },
        }

    # Map agent response to frontend format
    fs = json_obj.get("financial_signals", {})

    def _norm_money(val):
        """Normalize a money value to the frontend's expected shape."""
        if val is None:
            return None
        if isinstance(val, dict):
            amt = val.get("amount")
            if amt is None:
                return None
            return {
                "amount": amt,
                "currency": val.get("currency", currency),
                "converted_amount": val.get("converted_amount", amt),
                "converted_currency": val.get("converted_currency", currency),
            }
        return None

    def _norm_obligations(obls):
        if not obls or not isinstance(obls, dict):
            return None
        result = {}
        for key, val in obls.items():
            normed = _norm_money(val)
            if normed:
                result[key] = normed
        return result if result else None

    # Extract summary
    raw_summary = json_obj.get("summary", "")
    if isinstance(raw_summary, dict):
        summary_text = raw_summary.get("text", str(raw_summary))
        country_ctx = raw_summary.get("country_context", "")
        currency_ctx = raw_summary.get("currency_context", "")
    else:
        summary_text = str(raw_summary)
        country_ctx = fs.get("country_context", "")
        currency_ctx = fs.get("currency_context", f"Target currency: {currency}")

    return {
        "summary": {
            "text": summary_text,
            "country_context": country_ctx,
            "currency_context": currency_ctx,
        },
        "financial_signals": {
            "monthly_income": _norm_money(fs.get("monthly_income")),
            "annual_income": _norm_money(fs.get("annual_income")),
            "outstanding_loan_balances": _norm_money(fs.get("outstanding_loan_balances")),
            "credit_card_balances": _norm_money(fs.get("credit_card_balances")),
            "recurring_obligations": _norm_obligations(fs.get("recurring_obligations")),
        },
        "missing_signals": json_obj.get("missing_signals", []),
        "processing_metadata": {
            "date_processed": (
                json_obj.get("document_metadata", {}).get("processed_timestamp")
                or json_obj.get("processing_metadata", {}).get("date_processed")
                or _now_iso()
            ),
            "tools_used": (
                json_obj.get("processing_metadata", {}).get("tools_used")
                or ["watsonx Orchestrate", "Granite LLM"]
            ),
            "notes": (
                json_obj.get("processing_metadata", {}).get("notes")
                or f"{num_files} file(s) analyzed via IBM watsonx Orchestrate."
            ),
        },
    }


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# ── Request/Response models ──────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    file_ids: list[str]
    target_language: str = "en"
    target_currency: str = "USD"


class UploadResponse(BaseModel):
    file_ids: list[str]


# ── 1. Upload endpoint ──────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse)
async def upload_files(
    files: list[UploadFile],
    user: User = Depends(get_current_user),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    allowed = {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/tiff",
    }
    file_ids: list[str] = []

    for f in files:
        if f.content_type not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {f.content_type}",
            )

        content = await f.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"File too large: {f.filename}")

        file_id = f"{uuid.uuid4()}{Path(f.filename).suffix}"
        dest = UPLOAD_DIR / file_id
        dest.write_bytes(content)
        file_ids.append(file_id)

    return UploadResponse(file_ids=file_ids)


# ── 2. Analyze endpoint ─────────────────────────────────────────────

@router.post("/analyze")
async def analyze(
    body: AnalyzeRequest,
    user: User = Depends(get_current_user),
):
    if not body.file_ids:
        raise HTTPException(status_code=400, detail="file_ids array required")

    # Verify all files exist
    for fid in body.file_ids:
        if not (UPLOAD_DIR / fid).exists():
            raise HTTPException(status_code=404, detail=f"File not found: {fid}")

    # Extract text from all files
    all_text_parts: list[str] = []
    for fid in body.file_ids:
        file_path = UPLOAD_DIR / fid
        try:
            text = _extract_text(file_path)
            if text.strip():
                all_text_parts.append(f"=== File: {fid} ===\n{text}")
        except Exception as e:
            all_text_parts.append(f"=== File: {fid} ===\n[Text extraction failed: {e}]")

    if not all_text_parts:
        raise HTTPException(status_code=400, detail="Could not extract text from any uploaded file")

    combined_text = "\n\n".join(all_text_parts)

    # If Orchestrate is configured, call the real agent
    if settings.wxo_mcsp_apikey and settings.wxo_instance_url and settings.wxo_agent_id:
        try:
            return await _call_orchestrate_agent(
                extracted_text=combined_text,
                target_language=body.target_language,
                target_currency=body.target_currency,
                num_files=len(body.file_ids),
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to call watsonx Orchestrate agent: {str(e)}",
            )

    # Fallback: demo response
    return _demo_response(body, user)


def _demo_response(body: AnalyzeRequest, user: User) -> dict:
    """Return a realistic demo response when no external agent is configured."""
    lang_labels = {"en": "English", "fr": "French", "es": "Spanish", "de": "German"}
    target_lang = lang_labels.get(body.target_language, body.target_language)
    cur = body.target_currency

    return {
        "summary": {
            "text": (
                f"Analysis of {len(body.file_ids)} document(s) for {user.full_name}. "
                f"Documents show a stable financial profile with consistent income deposits "
                f"and responsible debt management. All values converted to {cur}."
            ),
            "country_context": (
                "Documents originate from a jurisdiction with standard banking regulations. "
                "Income verification aligns with local employment norms."
            ),
            "currency_context": (
                f"All monetary values have been converted to {cur} using current exchange rates."
            ),
        },
        "financial_signals": {
            "monthly_income": {
                "amount": 4200.00,
                "currency": "USD",
                "converted_amount": 4200.00 if cur == "USD" else 3850.00,
                "converted_currency": cur,
            },
            "annual_income": {
                "amount": 50400.00,
                "currency": "USD",
                "converted_amount": 50400.00 if cur == "USD" else 46200.00,
                "converted_currency": cur,
            },
            "outstanding_loan_balances": {
                "amount": 12500.00,
                "currency": "USD",
                "converted_amount": 12500.00 if cur == "USD" else 11460.00,
                "converted_currency": cur,
            },
            "credit_card_balances": {
                "amount": 1830.00,
                "currency": "USD",
                "converted_amount": 1830.00 if cur == "USD" else 1678.00,
                "converted_currency": cur,
            },
            "recurring_obligations": {
                "rent": {
                    "amount": 1450.00,
                    "currency": "USD",
                    "converted_amount": 1450.00 if cur == "USD" else 1329.00,
                    "converted_currency": cur,
                },
                "utilities": {
                    "amount": 120.00,
                    "currency": "USD",
                    "converted_amount": 120.00 if cur == "USD" else 110.00,
                    "converted_currency": cur,
                },
                "insurance": {
                    "amount": 280.00,
                    "currency": "USD",
                    "converted_amount": 280.00 if cur == "USD" else 257.00,
                    "converted_currency": cur,
                },
            },
        },
        "missing_signals": [],
        "processing_metadata": {
            "date_processed": _now_iso(),
            "tools_used": ["watsonx.ai Text Extraction", "Granite LLM"],
            "notes": (
                f"Demo response — no external agent configured. "
                f"{len(body.file_ids)} file(s) received. Target: {target_lang}/{cur}."
            ),
        },
    }
