# Community Engagement ML

Rank local businesses by community engagement propensity using proxy-supervision and Random Forest.

**Problem**: You want to approach local businesses for community partnerships, but you have only a handful of known outcomes (e.g., 14 responses) — far too few to train a classifier directly.

**Solution**: Train on a correlated **proxy label** — a stand-in for the outcome you actually want. For example, Chamber of Commerce membership is a natural proxy for community engagement: members have already demonstrated they invest in their community. With ~75 proxy-positive businesses out of 500, we have enough signal to train a Random Forest. Score every unlabeled business and validate against a small held-out outcome set (e.g., 14 known partnership responses).

**Result**: A ranked priority list that captures non-obvious high-potential businesses — including those the proxy label misses. The codebase uses `proxy_*` / `outcome_*` naming throughout; swap in any proxy signal that fits your domain.

## Methodology

| Component | Detail |
|---|---|
| **Proxy supervision** | Train on a correlated but abundant label (e.g., Chamber membership at ~15% rate) to predict a sparse outcome |
| **Feature engineering** | 30+ features from raw business data: online presence flags, category dummies, review metrics |
| **Model** | Random Forest (300 trees, max_depth=8, balanced class weights) |
| **Validation** | Counterfactual: do held-out known outcomes rank above baseline? |
| **Metric** | ROC-AUC ~0.72–0.75 cross-validated |

## Repo Structure

```
├── notebooks/
│   └── community_engagement_ml.ipynb  # Main Voila dashboard — run this
├── data/
│   └── demo/                     # Pre-sanitized demo data (real data, PII scrubbed)
├── pipeline/                     # Full production data pipeline scripts
│   ├── README.md                 # Pipeline documentation
│   ├── dedup_gmaps.py            # Business deduplication
│   ├── generate_review_pairs.py  # Candidate match generation
│   ├── merge_datasets.py         # Data merging
│   └── queries/                  # Overture→Google Maps query mappings
├── Dockerfile                    # Voila container for Hugging Face Spaces
├── voila.json                    # Voila configuration
└── pyproject.toml                # Dependencies
```

## Quick Start

```bash
# Launch the dashboard (demo data ships pre-generated)
voila notebooks/community_engagement_ml.ipynb
```

### Docker

```bash
docker build -t community-engagement-ml .
docker run -p 7860:7860 community-engagement-ml
```

Then open http://localhost:7860.

## The Pipeline (for real data)

See `pipeline/README.md` for the full pipeline:

1. Query Overture Maps for any area's business ecosystem
2. Enrich profiles via Google Maps scraper (third-party Docker)
3. Deduplicate, match against a proxy label source, merge outcome records
4. Train the same ML model on real data
5. Generate a priority outreach list

## On Demo Data

`data/demo/business_data_merged.csv` contains real business data with all PII (names, phones, addresses, websites) scrubbed. The feature distributions and label correlations are genuine — so the ML results you see in the notebook are representative. The pipeline directory contains the production scripts for running on your own data.
