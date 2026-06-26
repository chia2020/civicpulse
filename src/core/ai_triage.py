from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from langchain_core.messages import HumanMessage

from src.config import load_environment

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_OLLAMA_MODEL = "llama3"
LOGGER = logging.getLogger(__name__)

_TRIAGE_PROMPT_TEMPLATE = (
    "Analyze the following civic issue description in Hyderabad, India:\n"
    '"{description}"\n\n'
    "Estimate the following parameters on a scale of 0.0 to 10.0 (where 0 is lowest and 10 is highest):\n"
    "1. severity: Immediate danger to life, safety, public health, or severe road risk.\n"
    "2. frequency: How likely this issue affects many people/commuters or indicates a systemic problem (default 3.0 if unclear).\n"
    "3. compounding_risk: Environment/seasonal risk factors (e.g. monsoon drainage clogging, extreme summer water cuts).\n"
    "Also, generate a concise, descriptive title (5 to 8 words) for the issue in English.\n\n"
    'You MUST return the output strictly as a JSON object with these keys: '
    '"severity" (float), "frequency" (float), "compounding_risk" (float), "title" (string).\n'
    "Do not include any markup, explanations, or backticks around the JSON."
)


def _get_llm(timeout_seconds: int):
    """Return the best available LLM client.

    Priority:
    1. Ollama (local open-source, if OLLAMA_BASE_URL is set).
    2. Gemini (cloud, if GEMINI_API_KEY is set).
    Returns None if neither is available.
    """
    load_environment()
    ollama_url = os.getenv("OLLAMA_BASE_URL")
    if ollama_url:
        try:
            from langchain_ollama import ChatOllama  # type: ignore[import-untyped]
            model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
            LOGGER.info("AI triage: using Ollama at %s model=%s", ollama_url, model)
            return ChatOllama(model=model, base_url=ollama_url, temperature=0)
        except ImportError:
            LOGGER.warning("langchain_ollama not installed; falling back to Gemini.")

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GENERATIVE_AI_API_KEY")
    if gemini_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
            LOGGER.info("AI triage: using Gemini model=%s", model)
            return ChatGoogleGenerativeAI(
                model=model,
                temperature=0,
                max_tokens=256,
                timeout=timeout_seconds,
                google_api_key=gemini_key,
            )
        except ImportError:
            LOGGER.warning("langchain_google_genai not installed.")

    return None


def estimate_issue_parameters(description: str, timeout_seconds: int = 10) -> dict[str, Any]:
    """Estimate Severity (S), Frequency (F), Compounding Risk (R) and generate a title.

    Uses Ollama if OLLAMA_BASE_URL is set, otherwise Gemini.
    Falls back to safe defaults if no LLM is available or the call fails.
    """
    load_environment()

    default_result: dict[str, Any] = {
        "severity": 5.0,
        "frequency": 3.0,
        "compounding_risk": 5.0,
        "title": (description.split(".")[0][:60] or "Hyderabad civic issue"),
    }

    if not description.strip():
        LOGGER.warning("Empty description. Using default triage parameters.")
        return default_result

    llm = _get_llm(timeout_seconds)
    if llm is None:
        LOGGER.warning("No LLM backend available. Using default triage parameters.")
        return default_result

    prompt = _TRIAGE_PROMPT_TEMPLATE.format(description=description[:3000])

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = str(response.content).strip()

        # Extract JSON even if wrapped in backtick code fences
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            content = match.group(0)

        data = json.loads(content)
        return {
            "severity": float(data.get("severity", 5.0)),
            "frequency": float(data.get("frequency", 3.0)),
            "compounding_risk": float(data.get("compounding_risk", 5.0)),
            "title": str(data.get("title") or default_result["title"]).strip(),
        }
    except Exception as exc:
        LOGGER.error("Failed to estimate issue parameters using AI: %s", exc, exc_info=True)

    return default_result
