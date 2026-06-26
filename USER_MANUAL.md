
# User Manual

## 1. Welcome to CivicPulse

CivicPulse is an advanced, automated pipeline that actively monitors the digital public square across Hyderabad's **Greater Hyderabad Municipal Corporation (GHMC)** zones. By aggregating unstructured data from regional newspapers (*The Hindu Hyderabad*, *Telangana Today*) and social media (*Twitter/X*, *Reddit r/hyderabad*), CivicPulse extracts, geocodes, and mathematically prioritizes localized civic grievances before they turn into major structural failures.

This manual provides an in-depth operational guide to using the **CivicPulse Proof of Concept (POC) Dashboard**, interpreting its predictive data layers, and utilizing its analytical frameworks for proactive municipal governance.

---

## 2. Main Interface Overview

The CivicPulse dashboard is designed as a single-window triage interface partitioned into four primary logical segments:

1. **Live Aggregated Metrics (Top Banner):** High-level summary of ongoing civic distress metrics across the entire city.
2. **Interactive Issue Queue (Left Panel):** A filtered, sorted, searchable register of active localized grievances with visual ranking badges and summary details.
3. **Geographic Zone Heatmap (Right Top Panel):** An SVG-based dynamic visual mapping tool representing issue density across the 6 major zones of Hyderabad.
4. **Impact Score Breakdown & Historical Trends (Right Bottom & Footer Panels):** Granular analytical views showing exactly how an issue's priority was calculated, alongside a 14-day chronological trend of city-wide report frequencies.

---

## 3. Core Metrics & Key Performance Indicators (KPIs)

Located at the top of the interface, these cards give an immediate assessment of Hyderabad's overall urban health:

* **Active Issues:** The current total volume of unique, deduplicated open grievances (e.g., `847` active cases). High numbers indicate localized backlogs.
* **Critical (Score ≥ 8):** A high-priority sub-metric tracking severe emergency situations (e.g., `63` cases). These require instant municipal deployment.
* **Zones Affected:** The number of GHMC administrative zones experiencing active reports (`6 / 6`), indicating whether an issue is systemic or localized.
* **Resolved (30d):** A trailing 30-day velocity metric (e.g., `312` resolved cases) indicating municipal response efficiency and clearance rates.

---

## 4. The Predictive Impact Scoring Model

Every issue captured by the AI synthesis layer is subjected to a strict, multi-parameter mathematical model to ensure geometric fairness and remove human reporting bias.

### The Formula

$$\text{Impact Score} = (S \times 0.30) + (F \times 0.25) + (R \times 0.20) + (D \times 0.15) + (P \times 0.10)$$

*All individual parameters are dynamically scaled on a **0 to 10** range by the LLM processing and analytical pipelines prior to weight distribution. The final score is bound between 0.0 and 10.0.*

### Parameter Definition and Rationale

| Parameter | Symbol | Weight | Functional Description |
| --- | --- | --- | --- |
| **Severity** | $S$ | **30%** (`0.30`) | Evaluates immediate public danger, structural risk, and linguistic urgency cues in the text. This is the primary triage criterion. |
| **Frequency** | $F$ | **25%** (`0.25`) | A spatially-clustered count of independent or duplicate reports regarding the exact same issue in a locality. Validates the objective truth and scale of the complaint. |
| **Compounding Risk** | $R$ | **20%** (`0.20`) | Environmental and temporal amplifier. For example, a drainage bottleneck scores higher right before the Hyderabad monsoon season; a power failure scores higher during peak summer heat. |
| **Issue Duration** | $D$ | **15%** (`0.15`) | Time elapsed since the initial report, normalized against a 30-day window. Acts as an aging factor to ensure chronic, long-standing problems are not buried by newer data. |
| **Population Density** | $P$ | **10%** (`0.10`) | Structural context factor mapped to the population density of the specific Hyderabad locality (e.g., dense pockets like Kukatpally or Secunderabad score higher than outer peripheral limits). |

### Visual Score Thresholds

Issues are color-coded based on their final score to streamline the triage queue:

* Critical (Score ≥ 8.0): Red badge. Immediate threat to life, safety, or widespread public grid disruption.
* High (Score 7.0 – 7.9): Orange/Yellow badge. Significant structural failures causing severe local impact.
* Medium (Score 6.0 – 6.9): Green badge. Standard infrastructure repairs or maintenance backlogs.
* Low (Score < 6.0): Grey badge. Nuisance or aesthetic issues with low immediate escalation risk.

---

## 5. Step-by-Step Operations Guide

### A. Searching and Filtering the Queue

1. Navigate to the toolbar directly above the issue list on the left side.
2. **Text Search:** Type into the search input box (`"Search locality or issue..."`). This executes a live filter against issue titles (e.g., *"Pothole"*) as well as specific localized neighborhoods (e.g., *"Mehdipatnam"*, *"LB Nagar"*, *"Ameerpet"*).
3. **Category Selection:** Click the category dropdown menu to instantly isolate specific urban sub-sectors. Select between:
* `Roads` (e.g., Potholes, broken pathways, metro construction blockages)
* `Water` (e.g., Supply cuts, low pressure, broken main lines)
* `Power` (e.g., Transformer faults, unlit streetlights)
* `Sanitation` (e.g., Garbage accumulation, waste dumping)
* `Drainage` (e.g., Waterlogging risks, clogged storm drains)



### B. Utilizing Advanced Sorting Mechanisms

CivicPulse allows three custom sorting arrays located in the `cp-sort-group` toolbar toggle buttons. Selecting a mode restructures the layout hierarchy:

* **Impact Score Sort (Default):** Organizes issues from a score of `10.0` down to `0.0`. Use this for standard daily emergency resource distribution.
* **Peak Traction Date Sort:** Restructures the list chronologically based on the exact calendar day an issue saw the *highest surge of online engagement, shares, and viral social media traction*. Use this to spot rapidly escalating public relations or community distress issues.
* **Post Date Sort:** Standard linear chronological sorting based on the date the AI layer first discovered the issue. Excellent for managing baseline operations and auditing response delays.

### C. Analyzing the Locality & Score Breakdown

1. Scroll through the left pane and click on any individual active issue row.
2. The selected row will highlight in soft teal (`#E1F5EE`).
3. Look at the **Right Panel** under **Impact Score Breakdown**:
* The container will change from its empty placeholder state to a live graphical horizontal bar indicator.
* Review the exact raw values ($0 - 10$) alongside the corresponding localized mathematical weights assigned to $S, F, R, D,$ and $P$.
* This gives an auditable look into why an issue is positioned where it is in the queue, preventing operational bias.



### D. Interpreting the Regional Heatmap

The **Hyderabad Zone Heatmap** on the top right gives macro-level situational awareness:

* **Color Schemes:**
* Coral (#F0997B): High Density Zones (e.g., *Central Zone* with `193 issues`).
* Warm Gold (#FAC775): Medium Density Zones (e.g., *West Zone* with `172 issues`).
* Soft Teal (#9FE1CB): Lower Density Zones (e.g., *Secunderabad* or *South Zone*).


* Cross-reference the active issues list against the heatmap to allocate regional contractors or ward supervisors efficiently to zones with heavy clustering.

### E. Monitoring the 14-Day Trend View

At the bottom of the user interface sits the line chart mapping total citywide report volumes over a trailing 14-day window.

* **Usage:** Monitor the slope of the line. A sharp positive spike indicates an expanding environmental or infrastructure emergency across the city (such as a sudden unseasonal cloudburst or grid failure). A steady downward slope indicates municipal resolution efforts are outpacing incoming public complaints.

---

## 6. Target Audience & Practical Use Cases

* **GHMC Officials & City Administrators:** Use the default **Impact Score** view every morning to dispatch repair trucks, sanitary workers, and engineering teams to the highest-risk hotspots across Hyderabad's 150+ administrative wards.
* **Ward Counselors & Local Inspectors:** Filter the dashboard by your specific localized keywords (e.g., inputting *"Malakpet"* or *"Uppal"*) to build your regional daily oversight agenda.
* **Urban Planners:** Filter the dashboard by specific categories like `Drainage` or `Roads` and analyze the 14-day trend line alongside the geographic heatmap to identify systemic infrastructure deficits requiring long-term capital investments.

---

## 7. Protocol for Managing User Feedback & Incorporating Changes

To maintain system precision, CivicPulse relies on a closed-loop feedback mechanism. This ensures that observations from ground-level engineers, administrative staff, and public users are safely processed and coded back into the application framework.

### A. Feedback Ingestion Channels

Feedback is captured via three core vectors integrated directly inside the pipeline environment:

1. **The In-App Override Button:** Located alongside the *Impact Score Breakdown*, allowing GHMC administrative users to flag misclassified issues or incorrect regional boundaries.
2. **System Discrepancy Logs:** Automated error logs generated when an LLM fails to safely resolve a dynamic location context (e.g., parsing ambiguous colloquial neighborhood names in Hyderabad).
3. **Engineering Support Tickets:** Infrastructure performance adjustments submitted via the technical deployment repository.

### B. Triage & Impact Categorization Matrix

Every incoming operational request or bug report is categorized to determine the engineering intervention pathway:

| Category | Type | Example Scenario | Resolution Action |
| --- | --- | --- | --- |
| **Tier 1** | UI / Display Adjustments | Changing dashboard colors, adding text tooltips, or fixing layout clipping on mobile screens. | **Front-end Patch:** Modified via CSS/React code updates without disturbing data pipelines. |
| **Tier 2** | Data & Keyword Mapping | A newly built metro station creates localized detours, or a new sub-locality name needs to be registered. | **Metadata Dictionary Update:** Update regional geocoding lookup parameters and configuration tables. |
| **Tier 3** | Pipeline & Model Logic | The dynamic AI parsing engine miscalculates severity ($S$), or the weight metrics require adjustment due to seasonal shift changes. | **Back-end & Config Deployment:** Requires updating configuration JSON parameters and running validation tests. |

### C. Standard Workflow for Code and Configuration Changes

When an update is approved (e.g., adjusting the Predictive Impact Scoring formula weights or introducing a new tracking category), the engineering team must follow this sequence:

1. **Local Configuration Isolation:** Avoid hardcoding parameters directly into the operational software stack. All core weights and thresholds reside in a central file (`config.json` or environmental variables).

```json
{
  "weights": {
    "severity": 0.30,
    "frequency": 0.25,
    "compounding_risk": 0.20,
    "issue_duration": 0.15,
    "population_density": 0.10
  }
}

```

2. **Iterative Local Testing:** Apply changes locally to a test repository. If tweaking the scoring configuration weights, process a historic data slice of 100 sample issues to ensure it yields balanced priorities.
3. **Staging Environment Validation:** Push the code modification to the `staging` dashboard branch. Ensure the UI components load successfully and data continues to populate without latency.
4. **Production Deployment:** Merge the approved patch into the production codebase during low-traffic maintenance windows (ideally between 01:00 AM and 04:00 AM IST) to prevent interface downtime for active municipal workers.

> ### ⚠️ Operational Security Guardrail
> 
> 
> Under no circumstances should the active data processing pipelines be modified or restarted during peak municipal working hours (08:00 AM – 08:00 PM IST). A failure in the staging validation test suite must trigger an immediate rollback to the previous functional software version tag to preserve operational stability.