# Data Pipeline

This directory contains the scripts for the full production pipeline used to generate business data, match against proxy labels, and train the ML model.

## Pipeline Steps

```
Overture Maps query
       ↓
Google Maps Scraper (third-party Docker tool)
       ↓
dedup_gmaps.py           — Deduplicate businesses by phone + fuzzy name
       ↓
generate_review_pairs.py — Generate candidate matches for review
label_pairs.py           — Interactive CLI for labeling matches
       ↓
merge_datasets.py        — Merge businesses, proxy labels, and outcome records
       ↓
notebook                 — Train Random Forest, generate priority list
```

## Requirements

- Python ≥3.12 with packages from `pyproject.toml`
- [google-maps-scraper](https://github.com/gosom/google-maps-scraper) (Docker) for Google Maps enrichment
- Overture Maps Python library: `pip install overturemaps`
- A proxy label source (e.g., Chamber of Commerce directory, community council roster)
- Outcome records (e.g., partnership/sponsorship tracking sheet)

## Quick Start

```bash
# Generate query list for your area from Overture Maps
python -c "
import overturemaps
bbox = [minx, miny, maxx, maxy]  # your bounding box
data = overturemaps.record_batch_reader('place', bbox)
# ... filter by locality, map categories to search terms
"

# Run Google Maps scraper (Docker)
docker run gosom/google-maps-scraper:v1.12.1 \
  -input queries.txt \
  -center lat,lng -radius 3000

# Deduplicate
python dedup_gmaps.py

# Generate and label proxy/outcome pairs
python generate_review_pairs.py
python label_pairs.py

# Merge all datasets
python merge_datasets.py

# Train ML model in the notebook
voila ../notebooks/community_engagement_ml.ipynb
```

## Environment Variables

| Variable | Description |
|---|---|
| `DEFINITIVE_JSON` | Path to raw business data JSON |
| `OUTPUT` | Path for output (varies by script) |
| `PROXY_CSV` | Path to proxy label CSV |
| `PROXY_PAIRS` | Path to labeled proxy match pairs CSV |
| `OUTCOME_PAIRS` | Path to labeled outcome match pairs CSV |

## Notes

- The `queries/` directory contains a sample Overture-to-Google-Maps query mapping for reference
- The `label_pairs.py` and `label_duplicates.py` scripts are interactive CLI tools — run in a terminal
- For a self-contained demo that doesn't require scraping, see `data/generate_demo_data.py` and the main notebook
