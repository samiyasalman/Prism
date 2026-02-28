"""IBM watsonx.ai Text Extraction — OCR + table extraction from PDFs/images."""

import asyncio
import logging

from ibm_watsonx_ai import APIClient, Credentials
from ibm_watsonx_ai.foundation_models.extractions import TextExtractions

from app.config import settings

logger = logging.getLogger(__name__)


def _get_client() -> APIClient:
    credentials = Credentials(url=settings.watsonx_url, api_key=settings.watsonx_api_key)
    return APIClient(credentials=credentials, project_id=settings.watsonx_project_id)


def start_extraction(cos_document_reference: str) -> str:
    """Start an async text extraction job. Returns the job ID."""
    client = _get_client()
    extraction = TextExtractions(
        api_client=client,
        project_id=settings.watsonx_project_id,
    )
    result = extraction.run(
        document_reference=cos_document_reference,
        results_reference=f"cos://{settings.cos_bucket}/extraction-results/",
        steps={"ocr": {"languages_list": ["en"]}, "tables_processing": {"enabled": True}},
    )
    job_id = result.get("metadata", {}).get("id", "")
    logger.info("Started text extraction job: %s", job_id)
    return job_id


def get_extraction_status(job_id: str) -> dict:
    """Check extraction job status. Returns {'status': ..., 'results': ...}."""
    client = _get_client()
    extraction = TextExtractions(
        api_client=client,
        project_id=settings.watsonx_project_id,
    )
    details = extraction.get_details(job_id)
    status = details.get("entity", {}).get("status", {}).get("state", "unknown")
    results_text = ""
    if status == "completed":
        results = details.get("entity", {}).get("results", [])
        for r in results:
            results_text += r.get("content", "")
    return {"status": status, "text": results_text}


async def extract_text_async(cos_document_reference: str) -> str:
    """Run extraction and poll until complete. Returns extracted text."""
    loop = asyncio.get_event_loop()
    job_id = await loop.run_in_executor(None, start_extraction, cos_document_reference)

    for _ in range(60):  # max 5 minutes
        await asyncio.sleep(5)
        result = await loop.run_in_executor(None, get_extraction_status, job_id)
        if result["status"] == "completed":
            return result["text"]
        if result["status"] in ("failed", "error"):
            raise RuntimeError(f"Text extraction failed for job {job_id}")

    raise TimeoutError(f"Text extraction timed out for job {job_id}")
