from __future__ import annotations

import os
import re

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from src.config import load_environment


GEMINI_MODEL = "gemini-1.5-flash"


def infer_hyderabad_locality(text: str, timeout_seconds: int = 12) -> str | None:
    load_environment()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or not text.strip():
        return None

    prompt = (
        "Extract the most specific Hyderabad, Telangana locality or landmark from this civic "
        "issue text. Return only the locality or landmark name. If no Hyderabad locality is "
        f"present, return UNKNOWN.\n\n{text[:4000]}"
    )

    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        temperature=0,
        max_tokens=24,
        timeout=timeout_seconds,
        google_api_key=api_key
    )

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        locality = str(response.content).strip()
    except Exception:
        return None

    locality = re.sub(r"[^A-Za-z0-9 &./'-]", "", locality).strip(" .")
    if not locality or locality.upper() == "UNKNOWN":
        return None
    return locality
