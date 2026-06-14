# Data Model: Performance Optimization

## New/Modified Entities

### LocalityCache
Used to store the mapping between raw area/text and resolved locality information to avoid redundant AI inference.

- **Field**: `text_hash` (Primary Key, SHA-256 of normalized input text)
- **Field**: `resolved_locality` (String, name of the locality/landmark)
- **Field**: `zone` (String)
- **Field**: `latitude` (Float)
- **Field**: `longitude` (Float)
- **Field**: `last_updated` (Timestamp)

### PipelineStatus (Runtime State)
Used to track the state of background ingestion.

- **Field**: `is_running` (Boolean)
- **Field**: `last_run_time` (Timestamp)
- **Field**: `issues_processed` (Integer)
- **Field**: `errors` (List of Strings)

## Validation Rules
- `text_hash` must be unique.
- `resolved_locality` should fallback to `Unknown` if inference fails.

## State Transitions
1. **Pipeline Idle**: `is_running = False`.
2. **Pipeline Started**: Triggered by background thread, `is_running = True`.
3. **Pipeline Finished**: `is_running = False`, update `last_run_time`.
