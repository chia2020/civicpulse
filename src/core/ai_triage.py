import json
import logging
import os
import re
from typing import Any
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from src.config import load_environment

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
LOGGER = logging.getLogger(__name__)


def estimate_issue_parameters(description: str, timeout_seconds: int = 10) -> dict[str, Any]:
    """Estimate Severity (S), Frequency (F), Compounding Risk (R) and generate a title using Gemini."""
    load_environment()
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GENERATIVE_AI_API_KEY")

    default_result = {
        "severity": 5.0,
        "frequency": 3.0,
        "compounding_risk": 5.0,
        "title": description.split(".")[0][:60] or "Hyderabad civic issue"
    }

    if not api_key or not description.strip():
        LOGGER.warning("GEMINI_API_KEY missing or empty description. Using default parameters.")
        return default_result

    prompt = (
        "Analyze the following civic issue description in Hyderabad, India:\n"
        f"\"{description[:3000]}\"\n\n"
        "Estimate the following parameters on a scale of 0.0 to 10.0 (where 0 is lowest and 10 is highest):\n"
        "1. severity: Immediate danger to life, safety, public health, or severe road risk.\n"
        "2. frequency: How likely this issue affects many people/commuters or indicates a systemic problem (default 3.0 if unclear).\n"
        "3. compounding_risk: Environment/seasonal risk factors (e.g. monsoon drainage clogging, extreme summer water cuts).\n"
        "Also, generate a concise, descriptive title (5 to 8 words) for the issue in English.\n\n"
        "You MUST return the output strictly as a JSON object with these keys: "
        "\"severity\" (float), \"frequency\" (float), \"compounding_risk\" (float), \"title\" (string).\n"
        "Do not include any markup, explanations, or backticks around the JSON."
    )

    llm = ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
        temperature=0,
        max_tokens=256,
        timeout=timeout_seconds,
        google_api_key=api_key,
    )

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = str(response.content).strip()

        # Simple json extraction regex in case LLM wraps it in backticks
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            content = match.group(0)

        data = json.loads(content)
        return {
            "severity": float(data.get("severity", 5.0)),
            "frequency": float(data.get("frequency", 3.0)),
            "compounding_risk": float(data.get("compounding_risk", 5.0)),
            "title": str(data.get("title") or default_result["title"]).strip()
        }
    except Exception as e:
        LOGGER.error(f"Failed to estimate issue parameters using AI: {e}", exc_info=True)

    return default_result
