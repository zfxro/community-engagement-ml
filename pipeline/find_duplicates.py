"""
Find candidate duplicate business pairs for manual review.

Uses three strategies to surface potential duplicates:
1. Exact phone match
2. Same phone-normalized match  
3. Same street + fuzzy name match (>= 0.80)

Outputs a CSV of candidate pairs for review_label_duplicates.py.
"""

import json, os, re
import pandas as pd
from rapidfuzz import fuzz

DEFINITIVE_JSON = os.environ.get("DEFINITIVE_JSON", "business_data.json")


def parse_street(comp_addr):
    if isinstance(comp_addr, dict):
        return str(comp_addr.get("street", "")).lower().strip()
    return ""


def full_address(row):
    """Reconstruct full address from complete_address dict."""
    ca = row.get("complete_address", {})
    if isinstance(ca, dict):
        parts = [ca.get("street", ""), ca.get("city", ""), ca.get("state", ""), ca.get("postal_code", "")]
        return ", ".join(p for p in parts if p)
    return row.get("address", "")


def normalize_phone(p):
    if not p or pd.isna(p):
        return ""
    digits = re.sub(r"\D", "", str(p))
    if len(digits) == 10:
        return digits
    if len(digits) == 11 and digits[0] == "1":
        return digits[1:]
    return ""


def find_candidates():
    with open(DEFINITIVE_JSON) as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    df["street"] = df["complete_address"].apply(parse_street)
    df["phone_norm"] = df["phone"].apply(normalize_phone)
    df["name_clean"] = df["title"].str.lower().str.strip()
    df["full_addr"] = df.apply(full_address, axis=1)

    street_groups = df.groupby("street")

    rows = []
    for street, group in street_groups:
        if not street or len(street) < 5:
            continue
        indices = group.index.tolist()
        if len(indices) < 2:
            continue

        for i in range(len(indices)):
            for j in range(i + 1, len(indices)):
                a = df.iloc[indices[i]]
                b = df.iloc[indices[j]]

                n_score = fuzz.WRatio(a["name_clean"], b["name_clean"]) / 100.0
                phone_match = 1.0 if (a["phone_norm"] and a["phone_norm"] == b["phone_norm"]) else 0.0

                # Only flag if phone matches OR names are very similar
                if phone_match != 1.0 and n_score < 0.75:
                    continue

                combined = n_score * 0.60 + phone_match * 0.40

                rows.append({
                    "street": street,
                    "a_full_address": a["full_addr"],
                    "a_title": a["title"],
                    "a_phone": a["phone"],
                    "a_category": a["category"],
                    "a_reviews": a["review_count"],
                    "a_rating": a["review_rating"],
                    "b_full_address": b["full_addr"],
                    "b_title": b["title"],
                    "b_phone": b["phone"],
                    "b_category": b["category"],
                    "b_reviews": b["review_count"],
                    "b_rating": b["review_rating"],
                    "name_score": round(n_score, 3),
                    "phone_match": phone_match,
                    "combined_score": round(combined, 3),
                    "is_duplicate": "",
                })

    out = pd.DataFrame(rows)
    out = out.sort_values("combined_score", ascending=False)
    out.to_csv("review_duplicates.csv", index=False)
    print(f"Found {len(out)} candidate duplicate pairs")
    phone_m = (out['phone_match']==1).sum()
    name_only = ((out['phone_match']!=1) & (out['name_score']>=0.75)).sum()
    print(f"  Phone match (same business, confident): {phone_m}")
    print(f"  Name ≥ 0.75 only (likely same, review): {name_only}")

    if len(out) > 0:
        print(f"\nHighest confidence:")
        for _, r in out.head(10).iterrows():
            print(f"  [{r['combined_score']:.2f}] {r['a_title']}  <->  {r['b_title']}")
    return out


if __name__ == "__main__":
    find_candidates()
