"""IBM watsonx.ai Granite LLM — structured financial data extraction."""

import asyncio
import json
import logging

from ibm_watsonx_ai import APIClient, Credentials
from ibm_watsonx_ai.foundation_models import ModelInference

from app.config import settings

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """Classify this financial document into exactly one category.
Categories: bank_statement, rent_receipt, utility_bill, pay_stub, other

Document text (first 2000 chars):
{text}

Respond with ONLY the category name, nothing else."""

EXTRACTION_PROMPT = """Extract financial transactions from this {doc_type} document.
Return a JSON array of transactions. Each transaction must have:
- "amount": number (positive for income/credit, negative for debits/expenses)
- "date": string in YYYY-MM-DD format (or null if unclear)
- "payee": string (who was paid or who paid)
- "description": brief description
- "category": one of [rent, income, utility, bank_transfer, groceries, other]
- "is_on_time": boolean (true if payment was on time, null if unknown)

Document text:
{text}

Return ONLY valid JSON array. No explanation."""


def _get_model() -> ModelInference:
    credentials = Credentials(url=settings.watsonx_url, api_key=settings.watsonx_api_key)
    client = APIClient(credentials=credentials, project_id=settings.watsonx_project_id)
    return ModelInference(
        model_id="ibm/granite-3-8b-instruct",
        api_client=client,
        project_id=settings.watsonx_project_id,
        params={
            "max_new_tokens": 4096,
            "temperature": 0.1,
            "repetition_penalty": 1.05,
        },
    )


async def classify_document(text: str) -> str:
    """Classify document type using Granite LLM."""
    loop = asyncio.get_event_loop()
    model = _get_model()
    prompt = CLASSIFICATION_PROMPT.format(text=text[:2000])
    result = await loop.run_in_executor(None, model.generate_text, prompt)
    classification = result.strip().lower()
    valid = {"bank_statement", "rent_receipt", "utility_bill", "pay_stub", "other"}
    return classification if classification in valid else "other"


async def extract_transactions(text: str, doc_type: str) -> list[dict]:
    """Extract structured transaction data using Granite LLM."""
    loop = asyncio.get_event_loop()
    model = _get_model()
    prompt = EXTRACTION_PROMPT.format(doc_type=doc_type, text=text[:8000])
    result = await loop.run_in_executor(None, model.generate_text, prompt)

    try:
        # Find JSON array in response
        start = result.index("[")
        end = result.rindex("]") + 1
        return json.loads(result[start:end])
    except (ValueError, json.JSONDecodeError):
        logger.error("Failed to parse LLM extraction result: %s", result[:500])
        return []
