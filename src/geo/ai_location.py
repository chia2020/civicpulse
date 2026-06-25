from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config import load_environment

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
CACHE_PATH = Path("storage/locality_cache.json")
LOGGER = logging.getLogger(__name__)


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
    # Use a simple normalized version of text as key to avoid massive keys
    key = re.sub(r"[^a-zA-Z0-9]", "", text.lower())[:100]
    cache[key] = locality

    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_PATH, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as exc:
        LOGGER.warning("Could not write locality cache: %s", exc)


async def ainfer_hyderabad_locality(text: str, timeout_seconds: int = 12) -> str | None:
    load_environment()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not text.strip():
        return None

    # Check cache first
    key = re.sub(r"[^a-zA-Z0-9]", "", text.lower())[:100]
    cache = _load_cache()
    if key in cache:
        return cache[key]

    prompt = (
        "Extract the most specific Hyderabad, Telangana locality or landmark from this civic "
        "issue text. Return only the locality or landmark name. If no Hyderabad locality is "
        f"present, return UNKNOWN.\n\n{text[:4000]}"
    )

    llm = ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
        temperature=0,
        max_tokens=24,
        timeout=timeout_seconds,
        google_api_key=api_key,
    )

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        locality = str(response.content).strip()
    except Exception:
        return None

    locality = re.sub(r"[^A-Za-z0-9 &./'-]", "", locality).strip(" .")
    if not locality or locality.upper() == "UNKNOWN":
        return None

    _save_to_cache(text, locality)
    return locality


def infer_hyderabad_locality(text: str, timeout_seconds: int = 12) -> str | None:
    load_environment()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not text.strip():
        return None

    # Check cache first
    key = re.sub(r"[^a-zA-Z0-9]", "", text.lower())[:100]
    cache = _load_cache()
    if key in cache:
        return cache[key]

    prompt = (
        "Extract the most specific Hyderabad, Telangana locality or landmark from this civic "
        "issue text. Return only the locality or landmark name. If no Hyderabad locality is "
        f"present, return UNKNOWN.\n\n{text[:4000]}"
    )

    llm = ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
        temperature=0,
        max_tokens=24,
        timeout=timeout_seconds,
        google_api_key=api_key,
    )

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        locality = str(response.content).strip()
    except Exception:
        return None

    locality = re.sub(r"[^A-Za-z0-9 &./'-]", "", locality).strip(" .")
    if not locality or locality.upper() == "UNKNOWN":
        return None

    _save_to_cache(text, locality)
    return locality
