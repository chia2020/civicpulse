# Research Findings: App Performance Optimization

## Decision: Implementation of Background Ingestion and Persistent Locality Mapping
The primary cause of the slow load time is the synchronous execution of the ingestion pipeline within the Streamlit main thread, combined with sequential LLM calls for locality inference. We will move the pipeline to a background execution model and implement a persistent mapping for localities.

## Rationale
- **User Perceived Latency**: By moving the pipeline to the background, the dashboard can immediately render existing data from the vector store while updating in the background.
- **Cost and Time Efficiency**: LLM calls are both slow and potentially expensive. Mapping known areas to localities persistently avoids redundant calls.

## Alternatives Considered
- **Parallel LLM Calls**: While `asyncio.gather` could speed up the pipeline, it still blocks the initial UI render if called synchronously at startup.
- **Server-Side Cron**: Moving ingestion to a separate service/cron job is ideal for production but increases infrastructure complexity for local development. A background thread in Streamlit is a better middle ground.

## Resolved Unknowns
### Latency Breakdown
- **Observation**: `refresh_live_issues_on_open` blocks the UI for the duration of `run_live_pipeline`.
- **Finding**: Each new issue requiring AI inference adds ~1-3 seconds (up to 12s timeout). 10 issues can easily exceed 20 seconds.

### Cache Efficiency
- **Observation**: `st.cache_data` only persists for the session/application lifetime and resets on code changes.
- **Finding**: We need a data-level cache (e.g., in the database or a local JSON/Parquet file) for resolved localities that survives app restarts.

### Vector Store Batching
- **Observation**: `upsert_issues` is already batch-capable.
- **Finding**: The bottleneck is the pre-processing (normalization/inference), not the database insertion.
