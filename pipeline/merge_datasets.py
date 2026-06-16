"""
Merge deduped business data with proxy labels and outcome records.

Reads the labeled review_proxy_pairs.csv and review_outcome_pairs.csv
to apply flags and outputs a single merged CSV for ML.

Usage:
    uv run python3 merge_datasets.py

Output:
    business_data_merged.csv
"""

import json, os, re, html
from collections import defaultdict

import pandas as pd

DEFINITIVE_JSON = os.environ.get("DEFINITIVE_JSON", "business_data_deduped.json")
PROXY_CSV = os.environ.get("PROXY_CSV", "proxy_members.csv")
PROXY_PAIRS = os.environ.get("PROXY_PAIRS", "review_proxy_pairs.csv")
OUTCOME_PAIRS = os.environ.get("OUTCOME_PAIRS", "review_outcome_pairs.csv")
OUTPUT = os.environ.get("OUTPUT", "business_data_merged.csv")


def normalize_phone(p):
    if not p or pd.isna(p):
        return ""
    digits = re.sub(r"\D", "", str(p))
    if len(digits) == 10:
        return digits
    if len(digits) == 11 and digits[0] == "1":
        return digits[1:]
    return ""


def main():
    print("Loading GMaps data...")
    with open(DEFINITIVE_JSON) as f:
        gmaps = pd.DataFrame(json.load(f))
    print(f"  {len(gmaps)} businesses")

    # --- Proxy labels ---
    print("Loading proxy labels...")
    proxy_src = pd.read_csv(PROXY_CSV)
    for c in ["name", "address", "category"]:
        if c in proxy_src.columns:
            proxy_src[c] = proxy_src[c].apply(
                lambda x: html.unescape(str(x)) if pd.notna(x) else x
            )

    pairs = pd.read_csv(PROXY_PAIRS)
    pairs["is_match"] = pairs["is_match"].astype(str)
    matched = pairs[pairs["is_match"] == "1.0"]

    title_to_proxy = {}
    for _, r in matched.iterrows():
        gtitle = str(r["gmaps_title"]).lower().strip()
        if gtitle not in title_to_proxy:
            title_to_proxy[gtitle] = {
                "proxy_name": r.get("proxy_name", r.get("chamber_name", "")),
                "proxy_category": r.get("proxy_category", r.get("chamber_category", "")),
            }

    gmaps["is_proxy_member"] = gmaps["title"].str.lower().str.strip().map(
        lambda t: t in title_to_proxy
    )
    gmaps["proxy_name"] = gmaps["title"].str.lower().str.strip().map(
        lambda t: title_to_proxy.get(t, {}).get("proxy_name", "")
    )
    gmaps["proxy_category"] = gmaps["title"].str.lower().str.strip().map(
        lambda t: title_to_proxy.get(t, {}).get("proxy_category", "")
    )

    proxy_matched = gmaps["is_proxy_member"].sum()
    print(f"  Proxy labels matched: {proxy_matched}/{len(proxy_src)}")

    # --- Outcome labels ---
    print("Loading outcome records...")
    sp = pd.read_csv(OUTCOME_PAIRS)
    sp["is_match"] = sp["is_match"].astype(str)
    matched_sp = sp[sp["is_match"] == "1"]

    title_to_outcome = defaultdict(lambda: {
        "is_approached": False,
        "outcome_positive": False,
        "outcome_negative": False,
        "outcome_amount": 0.0,
        "outcome_names": [],
    })
    for _, r in matched_sp.iterrows():
        gtitle = str(r["gmaps_title"]).lower().strip()
        info = title_to_outcome[gtitle]
        info["is_approached"] = True
        decision = r.get("outcome_decision", r.get("sponsor_decision", ""))
        if decision == "Yes":
            info["outcome_positive"] = True
        else:
            info["outcome_negative"] = True
        amt = r.get("outcome_amount", r.get("sponsor_amount", 0))
        if pd.notna(amt):
            try:
                info["outcome_amount"] += float(amt)
            except (ValueError, TypeError):
                pass
        info["outcome_names"].append(r.get("outcome_name", r.get("sponsor_name", "")))

    gmaps["is_approached_for_outcome"] = False
    gmaps["outcome_positive"] = 0
    gmaps["outcome_negative"] = 0
    gmaps["outcome_amount"] = 0.0
    gmaps["outcome_name_matched"] = ""

    for idx, row in gmaps.iterrows():
        gtitle = str(row["title"]).lower().strip()
        if gtitle in title_to_outcome:
            info = title_to_outcome[gtitle]
            gmaps.at[idx, "is_approached_for_outcome"] = True
            gmaps.at[idx, "outcome_positive"] = int(info["outcome_positive"])
            gmaps.at[idx, "outcome_negative"] = int(info["outcome_negative"])
            gmaps.at[idx, "outcome_amount"] = info["outcome_amount"]
            gmaps.at[idx, "outcome_name_matched"] = ", ".join(info["outcome_names"])

    gmaps["outcome_label"] = -1
    gmaps.loc[gmaps["outcome_positive"] == 1, "outcome_label"] = 1
    gmaps.loc[gmaps["outcome_negative"] == 1, "outcome_label"] = 0

    total_approached = gmaps["is_approached_for_outcome"].sum()
    print(f"  Outcome records matched: {total_approached}/{len(matched_sp)} matches from CSV")

    gmaps.to_csv(OUTPUT, index=False)
    print(f"\nSaved to {OUTPUT}")

    print(f"\n  Total businesses: {len(gmaps)}")
    print(f"  Proxy members: {proxy_matched}")
    print(f"  Approached for outcome: {total_approached}")
    print(f"  Positive: {(gmaps['outcome_label']==1).sum()}")
    print(f"  Negative: {(gmaps['outcome_label']==0).sum()}")
    print(f"  Unlabeled: {(gmaps['outcome_label']==-1).sum()}")

    print("\nMatched outcomes:")
    for _, r in gmaps[gmaps["is_approached_for_outcome"]].iterrows():
        label = "Yes" if r["outcome_label"] == 1 else "No"
        print(f"  {r['title']:45s} ${r['outcome_amount']:>6.0f} [{label}] ({r['outcome_name_matched']})")


if __name__ == "__main__":
    main()
