import json
import logging
import os
import re
from pathlib import Path
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from src.config import load_environment

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
LOGGER = logging.getLogger(__name__)
CACHE_PATH = Path("storage/translation_cache.json")

TRANSLATIONS = {
    "en": {
        "title": "CivicPulse",
        "caption": "AI-driven civic issue prioritization for Hyderabad GHMC zones",
        "search_label": "Search",
        "search_placeholder": "Search by area, category, or issue",
        "data_mgmt": "Data Management",
        "refresh_feed": "Refresh Feed",
        "refreshed_msg": "Applied {count} scraped issues ({duration:.1f}s)",
        "scraping_msg": "Scraping live sources... ({elapsed:.0f}s)",
        "refresh_failed": "Refresh failed: {error}",
        "dismiss": "Dismiss",
        "active_issues": "Active Issues",
        "critical_priority": "Critical Priority",
        "zones_affected": "Zones Affected",
        "resolved_30d": "Resolved (30d)",
        "hotspots": "Hotspots",
        "issue_queue": "Issue Queue",
        "loc_ghmc_zone": "Location / GHMC Zone",
        "category_label": "Category",
        "sort_by": "Sort Issues By",
        "direction": "Direction",
        "descending": "Descending",
        "ascending": "Ascending",
        "report_new_issue": "Report New Issue",
        "issue_cat": "Issue Category",
        "loc_landmark": "Location / Landmark",
        "issue_desc": "Issue Description",
        "open_ghmc_portal": "Open Official GHMC Grievance Portal",
        "submit_dashboard": "Submit to CivicPulse Dashboard & Map",
        "submit_success": "Issue submitted successfully! Geocoded zone: {zone}, coordinates: ({lat:.4f}, {lon:.4f})",
        "submit_failed": "Failed to submit issue: {error}",
        "report_ghmc": "Report to Official GHMC Portal",
        "post_date_label": "Post date",
        "peak_traction_label": "Peak traction",
        "source_label": "Source",
        "no_issues": "No issues found. Use the Refresh button in the sidebar to fetch data.",
        "updating_dashboard": "Updating dashboard...",
        "impact_score": "Impact Score",
        "location": "Location",
        "ghmc_zone": "GHMC Zone",
        "critical_priority_sort": "Critical Priority",
        "post_date_sort": "Post Date",
        "peak_traction_sort": "Peak Traction Date",
        "all": "All",
        # Categories
        "Drainage": "Drainage",
        "Roads": "Roads",
        "Water": "Water",
        "Sanitation": "Sanitation",
        "Street Lighting": "Street Lighting",
        "Power": "Power",
        "Traffic & Public Safety": "Traffic & Public Safety",
        "Urban Infrastructure": "Urban Infrastructure",
        "Uncategorized": "Uncategorized",
        # Zones
        "Central": "Central",
        "North": "North",
        "South": "South",
        "West": "West",
        "East": "East",
        "Secunderabad": "Secunderabad",
        "Unknown": "Unknown",
        # Urgency Labels
        "Critical": "Critical",
        "High": "High",
        "Medium": "Medium",
        "Low": "Low",
        "translate_desc": "Translate to Telugu",
        "translated_title": "Translated Title",
        "translated_desc": "Translated Description",
        "show_english": "Show English",
        "remove_duplicates": "Remove Duplicates",
        "duplicates_removed": "Deduplication done: removed {count} duplicate issues.",
    },
    "te": {
        "title": "సివిక్ పల్స్ (CivicPulse)",
        "caption": "హైదరాబాద్ GHMC జోన్ల కోసం AI-ఆధారిత పౌర సమస్యల ప్రాధాన్యత",
        "search_label": "శోధన",
        "search_placeholder": "ప్రాంతం, వర్గం లేదా సమస్య ద్వారా శోధించండి",
        "data_mgmt": "డేటా నిర్వహణ",
        "refresh_feed": "ఫీడ్ రిఫ్రెష్ చేయండి",
        "refreshed_msg": "{count} స్క్రాప్ చేయబడిన సమస్యలు విజయవంతంగా జోడించబడ్డాయి ({duration:.1f}సె)",
        "scraping_msg": "లైవ్ వనరులను స్క్రాప్ చేస్తోంది... ({elapsed:.0f}సె)",
        "refresh_failed": "రిఫ్రెష్ విఫలమైంది: {error}",
        "dismiss": "తీసివేయి",
        "active_issues": "క్రియాశీల సమస్యలు",
        "critical_priority": "తీవ్రమైన ప్రాధాన్యత",
        "zones_affected": "ప్రభావిత ప్రాంతాలు",
        "resolved_30d": "పరిష్కరించబడినవి (30 రోజులు)",
        "hotspots": "హాట్‌స్పాట్‌లు",
        "issue_queue": "సమస్యల క్యూ",
        "loc_ghmc_zone": "ప్రాంతం / GHMC జోన్",
        "category_label": "వర్గం",
        "sort_by": "సమస్యలను దీని ఆధారంగా క్రమబద్ధీకరించండి",
        "direction": "దిశ",
        "descending": "అవరోహణ",
        "ascending": "ఆరోహణ",
        "report_new_issue": "కొత్త సమస్యను నిവേదించండి",
        "issue_cat": "సమస్య వర్గం",
        "loc_landmark": "ప్రాంతం / మైలురాయి",
        "issue_desc": "సమస్య వివరణ",
        "open_ghmc_portal": "అధికారిక GHMC ఫిర్యాదుల పోర్టల్‌ను తెరవండి",
        "submit_dashboard": "సివిక్ పల్స్ డాష్‌బోర్డ్ & మ్యాప్‌కు సమర్పించండి",
        "submit_success": "సమస్య విజయవంతంగా సమర్పించబడింది! గుర్తించబడిన జోన్: {zone}, కోఆర్డినేట్లు: ({lat:.4f}, {lon:.4f})",
        "submit_failed": "సమస్యను సమర్పించడం విఫలమైంది: {error}",
        "report_ghmc": "అధికారిక GHMC పోర్టల్‌కు నివేదించండి",
        "post_date_label": "పోస్ట్ తేదీ",
        "peak_traction_label": "గరిష్ట ట్రాక్షన్",
        "source_label": "మూలం",
        "no_issues": "సమస్యలు ఏవీ కనుగొనబడలేదు. డేటాను పొందడానికి సైడ్‌బార్‌లో రిఫ్రెష్ బటన్ ఉపయోగించండి.",
        "updating_dashboard": "డాష్‌బోర్డ్ అప్‌డేట్ అవుతోంది...",
        "impact_score": "ఇంపాక్ట్ స్కోరు",
        "location": "ప్రాంతం",
        "ghmc_zone": "GHMC జోన్",
        "critical_priority_sort": "తీవ్రమైన ప్రాధాన్యత",
        "post_date_sort": "పోస్ట్ తేదీ",
        "peak_traction_sort": "గరిష్ట ట్రాక్షన్ తేదీ",
        "all": "అన్నీ",
        # Categories
        "Drainage": "డ్రైనేజీ",
        "Roads": "రోడ్లు",
        "Water": "నీరు",
        "Sanitation": "శుభ్రత",
        "Street Lighting": "వీధి దీపాలు",
        "Power": "విద్యుత్",
        "Traffic & Public Safety": "ట్రాఫిక్ & ప్రజా భద్రత",
        "Urban Infrastructure": "పట్టణ మౌలిక సదుపాయాలు",
        "Uncategorized": "వర్గీకరించబడనివి",
        # Zones
        "Central": "సెంట్రల్",
        "North": "నార్త్",
        "South": "సౌత్",
        "West": "వెస్ట్",
        "East": "ఈస్ట్",
        "Secunderabad": "సికింద్రాబాద్",
        "Unknown": "తెలియదు",
        # Urgency Labels
        "Critical": "తీవ్రమైనది",
        "High": "ఎక్కువ",
        "Medium": "మధ్యస్థం",
        "Low": "తక్కువ",
        "translate_desc": "తెలుగులోకి అనువదించండి",
        "translated_title": "అనువదించబడిన శీర్షిక",
        "translated_desc": "అనువదించబడిన వివరణ",
        "show_english": "ఇంగ్లీష్ చూపించు",
        "remove_duplicates": "నకిలీలను తొలగించు",
        "duplicates_removed": "నకిలీలు తొలగించబడ్డాయి: {count} నకిలీ సమస్యలు తొలగించబడ్డాయి.",
    }
}


def _load_cache() -> dict[str, str]:
    if not CACHE_PATH.exists():
        return {}
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items()}


def _save_to_cache(text: str, target_lang_code: str, translated: str) -> None:
    cache = _load_cache()
    # Key combines target language and normalized prefix of text
    normalized_key = re.sub(r"[^a-zA-Z0-9]", "", text.lower())[:100]
    key = f"{target_lang_code}:{normalized_key}"
    cache[key] = translated

    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        LOGGER.warning("Could not write translation cache: %s", exc)


def translate_text(text: str, target_lang_code: str = "te", timeout_seconds: int = 10) -> str:
    """Translate text to Telugu (te) or English (en) using Gemini, with file caching."""
    if not text or not text.strip():
        return text

    target_lang_code = target_lang_code.lower()
    if target_lang_code not in {"te", "en"}:
        return text

    # Check cache first
    normalized_key = re.sub(r"[^a-zA-Z0-9]", "", text.lower())[:100]
    cache_key = f"{target_lang_code}:{normalized_key}"
    cache = _load_cache()
    if cache_key in cache:
        return cache[cache_key]

    load_environment()
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_GENERATIVE_AI_API_KEY")
    if not api_key:
        LOGGER.warning("GEMINI_API_KEY not found. Skipping translation.")
        return text

    target_lang = "Telugu" if target_lang_code == "te" else "English"
    prompt = (
        f"Translate the following text to {target_lang}. "
        "Keep the translation natural and accurate. "
        "Do not add any explanations, preambles, or markdown formatting beyond the translated text.\n\n"
        f"{text[:4000]}"
    )

    llm = ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
        temperature=0.1,
        max_tokens=1000,
        timeout=timeout_seconds,
        google_api_key=api_key,
    )

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        translated = str(response.content).strip()
        if translated:
            _save_to_cache(text, target_lang_code, translated)
            return translated
    except Exception as e:
        LOGGER.error(f"AI translation failed: {e}")

    return text
