"""Streamlit Cloud entrypoint for CivicPulse.

The dashboard implementation lives in app.py. Importing it lets deployments
configured with main.py render the same Streamlit app.
"""

import app  # noqa: F401
