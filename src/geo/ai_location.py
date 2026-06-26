from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from langchain_core.messages import HumanMessage

from src.config import load_environment

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_OLLAMA_MODEL = "llama3"
CACHE_PATH = Path("storage/locality_cache.json")
LOGGER = logging.getLogger(__name__)

_LOCALITY_PROMPT_TEMPLATE = (
    "Extract the most specific Hyderabad, Telangana locality or landmark from this civic "
    "issue text. Return only the locality or landmark name. If no Hyderabad locality is "
    "present, return UNKNOWN.\n\n{text}"
)


def _load_cache() -> dict[str, str]:
    if not CACHE_PATH.exists():
        return {}
    try:
        with open(CACHE_PATH) as f:
            data = json.load(f)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


def _save_to_cache(text: str, locality: str) -> None:
    cache = _load_cache()
    key = re.sub(r"[^a-zA-Z0-9]", "", text.lower())[:100]
    cache[key] = locality
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_PATH, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as exc:
        LOGGER.warning("Could not write locality cache: %s", exc)


def _cache_key(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "", text.lower())[:100]


def _clean_locality(raw: str) -> str | None:
    """Sanitise and validate a raw LLM locality response."""
    cleaned = re.sub(r"[^A-Za-z0-9 &./'-]", "", raw).strip(" .")
    if not cleaned or cleaned.upper() == "UNKNOWN":
        return None
    return cleaned


def _get_llm(timeout_seconds: int):
    """Return the best available LLM client.

    Priority:
    1. Ollama (local open-source, if OLLAMA_BASE_URL is set or ollama is installed).
    2. Gemini (cloud, if GEMINI_API_KEY is set).
    Falls back to None if neither is available.
    """
    load_environment()
    ollama_url = os.getenv("OLLAMA_BASE_URL")
    if ollama_url:
        try:
            from langchain_ollama import ChatOllama  # type: ignore[import-untyped]
            model = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
            LOGGER.info("Using Ollama LLM at %s model=%s", ollama_url, model)
            return ChatOllama(model=model, base_url=ollama_url, temperature=0)
        except ImportError:
            LOGGER.warning("langchain_ollama not installed; skipping Ollama.")

    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GENERATIVE_AI_API_KEY")
    if gemini_key:
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            model = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
            LOGGER.info("Using Gemini LLM model=%s", model)
            return ChatGoogleGenerativeAI(
                model=model,
                temperature=0,
                max_tokens=24,
                timeout=timeout_seconds,
                google_api_key=gemini_key,
            )
        except ImportError:
            LOGGER.warning("langchain_google_genai not installed; skipping Gemini.")

    LOGGER.warning("No LLM backend available for locality inference.")
    return None


async def ainfer_hyderabad_locality(text: str, timeout_seconds: int = 12) -> str | None:
    """Async version: infer a Hyderabad locality from free-form text."""
    load_environment()
    if not text.strip():
        return None

    key = _cache_key(text)
    cache = _load_cache()
    if key in cache:
        return cache[key]

    llm = _get_llm(timeout_seconds)
    if llm is None:
        return None

    prompt = _LOCALITY_PROMPT_TEMPLATE.format(text=text[:4000])
    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        locality = _clean_locality(str(response.content).strip())
    except Exception as exc:
        LOGGER.warning("ainfer_hyderabad_locality failed: %s", exc)
        return None

    if locality:
        _save_to_cache(text, locality)
    return locality


def infer_hyderabad_locality(text: str, timeout_seconds: int = 12) -> str | None:
    """Sync version: infer a Hyderabad locality from free-form text."""
    load_environment()
    if not text.strip():
        return None

    key = _cache_key(text)
    cache = _load_cache()
    if key in cache:
        return cache[key]

    llm = _get_llm(timeout_seconds)
    if llm is None:
        return None

    prompt = _LOCALITY_PROMPT_TEMPLATE.format(text=text[:4000])
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        locality = _clean_locality(str(response.content).strip())
    except Exception as exc:
        LOGGER.warning("infer_hyderabad_locality failed: %s", exc)
        return None

    if locality:
        _save_to_cache(text, locality)
    return locality
