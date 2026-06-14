# Quickstart: Performance Optimization

## Overview
This feature introduces background data ingestion and persistent caching to the CivicPulse dashboard to improve load times.

## Prerequisites
- `requirements.txt` dependencies installed.
- Valid `GEMINI_API_KEY` in `.env`.

## Setup
1.  **Initialize Cache**: The application will automatically create a local `locality_cache.json` if it doesn't exist.
2.  **Run Dashboard**:
    ```bash
    streamlit run app.py
    ```

## Development
- **Diagnostics**: Check `streamlit.out.log` for performance telemetry.
- **Background Pipeline**: The pipeline now runs in a separate thread. Use the "Refresh" button in the sidebar to manually trigger a data sync without blocking the UI.
