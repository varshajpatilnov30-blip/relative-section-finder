# Relative Section Finder

A Streamlit dashboard for searching and comparing provisions in the Bharatiya Nyaya Sanhita, 2023.

## Run locally

Install the packages in requirements.txt, then run:

    streamlit run app.py

## Deploy

Deploy from a GitHub repository using Streamlit Community Cloud. Choose app.py as the entrypoint. Keep data/bns_sections.txt in the repository because the app reads it at startup.

The app uses the all-MiniLM-L6-v2 sentence-transformers model. The first semantic search may take longer while the model starts.

This tool supports legal research and does not provide legal advice.
