# CivicPulse – Geographical Expansion Plan

A structured roadmap for expanding CivicPulse beyond Hyderabad to other municipal regions across Telangana, Andhra Pradesh, and eventually other Indian metros.

---

## Phase 1 – Greater Hyderabad Consolidation (Month 1–2)

### Current Coverage
CivicPulse currently operates across the **6 primary GHMC zones**:
- Central, North, South, West, East, Secunderabad

### Expansion Target
- **Outer Ring Municipalities**: Shamshabad, Kompally, Medchal, Patancheru, Ghatkesar, Pocharam
- **HMDA Extended Areas**: Outer Ring Road (ORR) corridor localities, Adibatla, Yelahanka, Shamirpet

### Technical Requirements
| Task | Details |
|:-----|:--------|
| Locality database expansion | Add 100+ new sub-localities with GPS coordinates and population density scores. |
| Zone boundary redefinition | Introduce an `outer_zone` classification for peri-urban areas. |
| Data source expansion | Add RSS feeds from local Telangana news outlets covering outer suburbs. |

---

## Phase 2 – Tier-2 Telangana Cities (Month 3–4)

### Target Cities
| City | Municipal Body | Population | Priority |
|:-----|:---------------|:-----------|:---------|
| Warangal | GWMC | ~8.5 lakh | High |
| Karimnagar | KMC | ~3 lakh | Medium |
| Nizamabad | NMC | ~3.5 lakh | Medium |
| Khammam | KhMC | ~3 lakh | Medium |

### Adaptation Strategy
- **Modular zone configuration**: Create per-city configuration files (`src/geo/<city>.py`) with locality lookups, zone definitions, and coordinate data.
- **Shared pipeline**: Reuse the existing ingestion, scoring, and storage pipeline. City selection via an environment variable `CIVICPULSE_TARGET_CITY`.
- **Telugu-first content**: Most Tier-2 complaints arrive in Telugu. The existing multi-language AI translation layer handles this natively.

---

## Phase 3 – Andhra Pradesh Expansion (Month 5–6)

### Target Cities
| City | Municipal Body | Population | Priority |
|:-----|:---------------|:-----------|:---------|
| Visakhapatnam | GVMC | ~21 lakh | High |
| Vijayawada | VMC | ~11 lakh | High |
| Tirupati | TMC | ~4 lakh | Medium |
| Guntur | GMC | ~7 lakh | Medium |

### Key Adaptations
- **New data sources**: AP-specific news outlets (Eenadu, Sakshi, Andhra Jyothi RSS feeds).
- **Zone schema**: AP municipalities use ward-based systems rather than GHMC-style zones. Add a `ward` field alongside `zone`.
- **Geocoding**: Expand the AI locality inference prompt to include AP city context when the target city is set.

---

## Phase 4 – Pan-India Metro Scaling (Month 7–12)

### Priority Metros
1. **Bengaluru** (BBMP) – High volume of English + Kannada civic complaints online.
2. **Chennai** (GCC) – Strong social media civic activism community.
3. **Pune** (PMC) – Active Reddit and Twitter civic discourse.

### Architecture Changes Required
| Change | Rationale |
|:-------|:----------|
| Multi-tenant database schema | Separate issue tables per city to prevent cross-contamination. |
| Language model expansion | Add Kannada, Tamil, Marathi language support to the translator module. |
| City-specific scoring weights | Population density matrices and seasonal risk factors differ per geography. |
| Federated deployment | Allow each city to run its own CivicPulse instance with a shared codebase. |

---

## Expansion Checklist (Per New City)

For each new city onboarded, the following must be completed:

- [ ] Create `src/geo/<city>.py` with locality lookup table (minimum 50 entries).
- [ ] Define zone/ward boundaries and GPS coordinates.
- [ ] Add population density scores for each locality.
- [ ] Identify and configure 3+ local RSS/news data sources.
- [ ] Validate geocoding accuracy with 20+ test cases in `tests/test_<city>_geo.py`.
- [ ] Test the AI locality inference prompt with city-specific language.
- [ ] Update the UI city selector dropdown.
- [ ] Deploy and seed with ≥ 50 historical issues.

---

## Risk Mitigation

| Risk | Mitigation |
|:-----|:-----------|
| Incomplete locality data in new cities | Partner with local civic groups to crowdsource landmark databases. |
| Language accuracy for non-Telugu/English | Use Gemini's multilingual capabilities; validate with native speakers before launch. |
| Rate-limiting from new data sources | Implement per-source exponential backoff; respect `robots.txt` directives. |
| Divergent municipal structures | Abstract zone/ward logic behind a `MunicipalRegion` interface for plug-and-play city modules. |
