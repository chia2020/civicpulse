
# 🏙️ CivicPulse

### An AI-Driven Predictive Dashboard for Localized Civic Issue Identification and Escalation Tracking
> 📍 **Scoped for Hyderabad, Telangana** — Covering all zones under GHMC (Greater Hyderabad Municipal Corporation)

---


## 📌 Table of Contents

- [Problem Statement](#problem-statement)
- [Proposed Solution](#proposed-solution)
- [Core Architecture](#core-architecture--workflow)
- [Impact Score — Parameters & Weights](#impact-score--parameters--weights)
- [Dashboard Features](#dashboard-features)
- [Tech Stack](#tech-stack)
- [Value Proposition](#value-proposition--impact)
- [Getting Started](#getting-started)

---

## 🚨 Problem Statement

Traditional civic grievance mechanisms (such as municipal mobile apps or web portals) are fundamentally **reactive**. They rely heavily on active citizen initiatives to formally file a complaint, leading to:

- Severe **under-reporting** in underserved areas across Hyderabad's localities (Old City, Kukatpally, LB Nagar, etc.)
- **Delayed responses** from GHMC and local ward authorities
- Minor local issues escalating into **major structural or public safety failures** before resources are deployed

Citizens frequently and organically voice infrastructure and public utility grievances across regional news outlets (like *The Hindu – Hyderabad*, *Telangana Today*) and social media — but this data remains **unstructured, fragmented, and entirely unmonitored** by civic bodies.

---

## 💡 Proposed Solution

CivicPulse is an automated, AI-driven pipeline that actively listens to the **"digital public square"** across Hyderabad to detect, synthesize, and prioritize localized civic issues *before* they escalate.

The system:
1. Continuously collects unstructured data from Hyderabad-specific regional news feeds and public social media channels
2. Structures this information using Large Language Models (LLMs)
3. Maps the issues geographically across Hyderabad's neighbourhoods and GHMC zones
4. Ranks grievances using a **Predictive Impact Engine** based on a multi-parameter weighted score
5. Stores issue records in a local persistent **vector database** for semantic retrieval and dashboard filtering
6. Supports **date-based sorting** — by the date an issue received peak internet traction, or the date it was first reported

---

## 🏗️ Core Architecture & Workflow

```
[Data Ingestion] ──> [AI Synthesis Layer] ──> [Impact Scoring Engine] ──> [Vector DB] ──> [Civic Dashboard]
```

### Layer Breakdown

**1. 📥 Data Ingestion Layer**
Python-based ingestion pipelines using:
- RSS feeds from Hyderabad-focused regional newspapers
- Targeted scraping of localized social media spaces (Twitter/X locality hashtags, Reddit r/hyderabad, etc.)

**2. 🤖 AI Synthesis & Geocoding Layer**
An LLM processing pipeline that performs Named Entity Recognition (NER) to extract:
- **Issue Category** (e.g., sewage overflow, pothole, power outage, water scarcity)
- **Local Landmark / Area Name** (e.g., "near Mehdipatnam flyover", "Ameerpet metro exit")
- **Contextual Severity** — assessed from language tone, urgency cues, and surrounding context

**3. 📊 Predictive Impact Scoring Engine**
A weighted algorithmic model — see full parameter and weight breakdown below.

**4. 🧠 Vector Storage Layer**
Issue documents are persisted in `storage/civicpulse_vector.db` with deterministic text embeddings, enabling semantic search across area names, categories, issue descriptions, source metadata, and urgency signals without relying on JSON files.

**5. 🗺️ Visualization Layer**
A centralized geographic map dashboard (built via Streamlit + Leaflet) displaying dynamic **"hotspots"** of high-impact, unchecked civic issues across Hyderabad, sortable by score, post date, or peak traction date.

---

## 🧮 Impact Score — Parameters & Weights

Every reported issue is assigned a computed **Impact Score** using the following formula:

### Core Formula

```
Impact Score = (S × 0.30) + (F × 0.25) + (R × 0.20) + (D × 0.15) + (P × 0.10)
```

> Weights are normalized so they sum to **1.0**. Each raw parameter is scaled to a **0–10** range before applying weights, producing a final Impact Score between **0 and 10**.

---

### Parameter Definitions & Weight Rationale

| Parameter | Symbol | Weight | Raw Scale | Description |
|-----------|--------|--------|-----------|-------------|
| **Severity** | `S` | **0.30** | 0–10 | LLM-evaluated score based on immediate public danger and urgency of language in reports. Highest weight because public safety risk is the primary triage criterion. |
| **Frequency** | `F` | **0.25** | 0–10 | Normalized count of spatially-clustered duplicate reports for the same issue in the same locality. High weight because repeated independent reports validate the issue's reality and scale. |
| **Compounding Risk Multiplier** | `R` | **0.20** | 0–10 | Environmental/temporal amplifier (e.g., a waterlogging report before Hyderabad's monsoon season, or a power failure during peak summer heat). Reflects how much worse an issue is likely to get if left unattended. |
| **Issue Duration** | `D` | **0.15** | 0–10 | Time elapsed since the issue was first reported, normalized against a 30-day window. Longer-standing unresolved issues score higher, preventing chronic problems from being buried under new reports. |
| **Population Density Impact** | `P` | **0.10** | 0–10 | Score based on the population density of the affected Hyderabad locality (e.g., dense areas like Secunderabad or Kukatpally score higher than outskirts). Lowest weight since density is a structural context factor, not an urgency signal. |

---

### Weight Design Principles

- **Severity and Frequency dominate (55% combined)** — because the most dangerous and most-reported issues should unambiguously rise to the top.
- **Compounding Risk (20%)** — accounts for future escalation potential, not just current state.
- **Duration (15%)** — acts as an aging factor to surface neglected long-term issues.
- **Population Density (10%)** — provides geographic fairness context without overriding urgency signals.

---

## 📊 Dashboard Features

| Feature | Description |
|---------|-------------|
| 🗺️ **Hyderabad Heatmap** | Interactive map showing civic issue hotspots across all GHMC zones |
| 🔢 **Impact Score Ranking** | Issues sorted by the computed multi-parameter weighted score |
| 📅 **Sort by Post Date** | Sort all issues by the date they were first reported/posted, showing newest or oldest first |
| 📈 **Sort by Peak Traction Date** | Sort issues by the date on which they received the highest volume of internet activity and social engagement — surfaces issues that had a surge in public attention on a specific date |
| 🏷️ **Category Filter** | Filter by issue type — roads, water, power, sanitation, etc. |
| 📍 **Locality Drill-Down** | Zoom into specific neighbourhoods (Banjara Hills, Tolichowki, Malakpet, etc.) |
| ⏱️ **Duration Tracker** | Highlights long-standing unresolved issues that have aged past a threshold |
| 📊 **Trend View** | Shows issue frequency trends over time per GHMC zone |
| 🔎 **Vector Search** | Searches stored issue embeddings by locality, grievance type, or urgency context |

---

## 🛠️ Tech Stack

| Category | Tools / Libraries |
|----------|-------------------|
| **Backend & Data Processing** | Python, Pandas, crawl4ai, langchain |
| **AI & NLP** | Gemini API / Groq API / Llama-3 (via Ollama) — for NER, severity scoring, and geocoding inference |
| **Geocoding & Clustering** | `geopy` (landmark → lat/long for Hyderabad localities), string-match deduplication |
| **Date & Traction Analysis** | Timestamp indexing + engagement volume tracking for post date and peak traction date sorting |
| **Storage & Retrieval** | Local SQLite-backed vector database with deterministic hashed embeddings |
| **Frontend Dashboard** | Streamlit + Leaflet.js (interactive geographic mapping) |

---

## 🚀 Getting Started

```bash
pip install -r requirements.txt
python -m src.ingestion.pipeline
streamlit run app.py
```

The default pipeline seeds localized Hyderabad verification data into `storage/civicpulse_vector.db`.

For live deep scraping, set `GEMINI_API_KEY` in your environment and run:

```bash
python -m src.ingestion.pipeline --live
```

To target specific pages:

```bash
python -m src.ingestion.pipeline --live --url "https://www.reddit.com/r/hyderabad/search/?q=pothole&restrict_sr=1&sort=new"
```

---

## 🌍 Value Proposition & Impact

**From Reactive to Proactive Governance**
Shifts GHMC resource allocation from *fixing complaints* to *preventing systemic infrastructure failures* across Hyderabad's 150+ wards.

**Data-Driven Prioritization**
Eliminates human bias by mathematically ensuring high-risk, high-impact issues rise to the top of the queue — regardless of which ward or locality the complaint originates from.

**Date-Aware Intelligence**
By allowing sorting on both post date and peak traction date, CivicPulse lets officials distinguish between *newly emerging* issues and *resurging* ones — enabling different response strategies for each.

**Actionable Intelligence**
Provides GHMC officials, ward counselors, and urban planners a ready-to-use triage dashboard for targeted, prioritized maintenance across the city.

---


<p align="center">Built to bridge the gap between Hyderabad's citizen voices and civic action. 🏛️</p>
