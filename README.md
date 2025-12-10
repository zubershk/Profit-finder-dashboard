# Profit-Finder Dashboard

A privacy-first, in-session Streamlit dashboard for quickly exploring e-commerce sales CSVs.

## Features
- In-memory ETL with self-healing parsing (dates, numbers)
- Manual schema editor with preview and one-click revert
- Derived revenue/cost/profit/margin when possible
- Plotly interactive charts: revenue over time, margin, top products, category share
- No DB, no disk storage: session-only processing

## Run locally
1. Create virtualenv (Python 3.9+)
2. pip install -r requirements.txt
3. streamlit run app.py

## Sample usage
- Inspect auto-detected schema in the Schema editor.
- Use Preview to inspect derived columns and diagnostics before applying.
- Apply mapping to reprocess session data and update dashboards.

## Notes
- For privacy, avoid uploading files with PII.
- For large files (100k+ rows) consider sampling or running in a machine with more memory.
