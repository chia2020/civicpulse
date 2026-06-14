# Implementation Plan: Optimize App Performance

## Technical Context
- **Current State**: Streamlit application (`app.py`) with a synchronous ingestion pipeline (`src/ingestion/pipeline.py`). Startup triggers `run_live_pipeline` which performs AI-based locality inference using `gemini-1.5-flash`.
- **Dependencies**: Streamlit, LangChain, Google Generative AI, Pandas, CivicVectorStore (Supabase).
- **Unknowns**:
  - Breakdown of latency between AI inference, database I/O, and Streamlit rendering. [NEEDS CLARIFICATION]
  - Overhead of current `st.cache_data` configuration. [NEEDS CLARIFICATION]
  - Batching capabilities of the `CivicVectorStore` for initial load. [NEEDS CLARIFICATION]

## Constitution Check
- **Constraint 1**: Maintain user data privacy during inference - **Compliant** (using standard enterprise AI patterns).
- **Constraint 2**: Ensure system resilience - **Needs improvement** (current synchronous calls can cause timeouts).

## Design
### Data Model
[Reference to data-model.md](data-model.md) - Focus on caching locality results and status flags for background ingestion.

### Interface Contracts
N/A - Internal performance optimization.

## Execution Phases
### Phase 0: Research
1.  **Startup Benchmarking**: Profile `app.py` and `pipeline.py` to pinpoint bottlenecks.
2.  **Concurrency Analysis**: Evaluate the impact of running the pipeline in a separate thread vs. main thread.
3.  **Cache Efficiency**: Test persistent caching strategies for `infer_hyderabad_locality`.

### Phase 1: Implementation
1.  **Instrumentation**: Add telemetry to track load times for diagnostics.
2.  **Async Refactoring**: Move `run_live_pipeline` to a background task.
3.  **Persistent Locality Cache**: Implement a lookup for previously resolved localities to skip LLM calls.
4.  **UI Feedback**: Add a non-blocking loading indicator for background data refreshes.

### Phase 2: Verification
1.  **Cold Start Test**: Verify initial load time is < 5 seconds.
2.  **Warm Start Test**: Verify subsequent loads are near-instant.
3.  **Interaction Test**: Verify search filters respond in < 1 second.
