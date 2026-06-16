"""
Deduplicate business data by phone number.

Primary dedup: same phone = same business (even at different addresses).
For entries without a phone, uses fuzzy name matching (>= 0.75) within
the same street address.

For merged groups:
    - Keeps the entry with the most reviews as base
    - Sums review_count across all merged entries
    - Weighted-average review_rating (by review_count)
    - Unions categories
    - Marks is_merged=True, merged_from=[list of merged place_ids]

Usage:
    uv run python3 dedup_gmaps.py
"""

import json, os, re
import pandas as pd
from rapidfuzz import fuzz

DEFINITIVE_JSON = os.environ.get("DEFINITIVE_JSON", "business_data.json")
OUTPUT = os.environ.get("OUTPUT", "business_data_deduped.json")


def normalize_phone(p):
    if not p or pd.isna(p):
        return ""
    digits = re.sub(r"\D", "", str(p))
    if len(digits) == 10:
        return digits
    if len(digits) == 11 and digits[0] == "1":
        return digits[1:]
    return ""


def parse_street(comp_addr):
    if isinstance(comp_addr, dict):
        return str(comp_addr.get("street", "")).lower().strip()
    return ""


def union_categories(cats_list):
    seen = set()
    result = []
    for c in cats_list:
        if isinstance(c, list):
            for item in c:
                if item not in seen:
                    seen.add(item)
                    result.append(item)
        elif c and c not in seen:
            seen.add(c)
            result.append(c)
    return result


def dedup():
    with open(DEFINITIVE_JSON) as f:
        data = json.load(f)
    print(f"Loaded {len(data)} businesses")

    df = pd.DataFrame(data)
    df["phone_norm"] = df["phone"].apply(normalize_phone)
    df["street"] = df["complete_address"].apply(parse_street)

    seen_place_ids = set()
    merged = []

    # --- Phase 1: phone-based dedup ---
    for phone, group in df.groupby("phone_norm"):
        if not phone:
            # Handle empty-phone entries separately
            continue
        indices = group.index.tolist()
        rows = [df.iloc[i] for i in indices]
        if len(rows) == 1:
            merged.append(rows[0].to_dict())
            continue
        base = max(rows, key=lambda r: (r["review_count"] or 0, 1 if r.get("web_site") else 0))
        total_reviews = sum(r["review_count"] or 0 for r in rows)
        weighted_rating = 0.0
        total_weight = 0
        for r in rows:
            cnt = r["review_count"] or 0
            rat = r["review_rating"] or 0
            if cnt > 0 and rat > 0:
                weighted_rating += rat * cnt
                total_weight += cnt
        avg_rating = round(weighted_rating / total_weight, 1) if total_weight > 0 else (base["review_rating"] or 0)
        all_cats = list(set(c for r in rows for c in (r.get("categories") or [])))
        merged_row = base.to_dict()
        merged_row["review_count"] = total_reviews
        merged_row["review_rating"] = avg_rating
        merged_row["categories"] = all_cats
        merged_row["merged_from"] = [r["place_id"] for r in rows if r["place_id"] != base["place_id"]]
        merged_row["is_merged"] = True
        merged.append(merged_row)

    # --- Phase 2: empty-phone dedup by street + name ---
    phone_empty = df[df["phone_norm"] == ""]
    for street, group in phone_empty.groupby("street"):
        if not street:
            for _, r in group.iterrows():
                merged.append(r.to_dict())
            continue
        indices = group.index.tolist()
        rows = [df.iloc[i] for i in indices]
        if len(rows) == 1:
            merged.append(rows[0].to_dict())
            continue

        # Cluster by fuzzy name within same street
        consumed = set()
        for i in range(len(rows)):
            if i in consumed:
                continue
            cluster = [rows[i]]
            consumed.add(i)
            for j in range(i + 1, len(rows)):
                if j in consumed:
                    continue
                n_score = fuzz.WRatio(
                    (rows[i].get("title") or "").lower().strip(),
                    (rows[j].get("title") or "").lower().strip()
                ) / 100.0
                if n_score >= 0.75:
                    cluster.append(rows[j])
                    consumed.add(j)

            if len(cluster) == 1:
                merged.append(cluster[0].to_dict())
            else:
                base = max(cluster, key=lambda r: (r["review_count"] or 0))
                total_reviews = sum(r["review_count"] or 0 for r in cluster)
                weighted_rating = 0.0
                total_weight = 0
                for r in cluster:
                    cnt = r["review_count"] or 0
                    rat = r["review_rating"] or 0
                    if cnt > 0 and rat > 0:
                        weighted_rating += rat * cnt
                        total_weight += cnt
                avg_rating = round(weighted_rating / total_weight, 1) if total_weight > 0 else (base["review_rating"] or 0)
                all_cats = list(set(c for r in cluster for c in (r.get("categories") or [])))
                merged_row = base.to_dict()
                merged_row["review_count"] = total_reviews
                merged_row["review_rating"] = avg_rating
                merged_row["categories"] = all_cats
                merged_row["merged_from"] = [r["place_id"] for r in cluster if r["place_id"] != base["place_id"]]
                merged_row["is_merged"] = True
                merged.append(merged_row)

    # Clean up helper fields + convert numpy types
    for r in merged:
        r.pop("phone_norm", None)
        r.pop("street", None)
        if "is_merged" not in r:
            r["is_merged"] = False
            r["merged_from"] = []
        for k, v in list(r.items()):
            if hasattr(v, "item"):
                r[k] = v.item()

    n_merged = int(sum(1 for r in merged if r["is_merged"]))
    print(f"After dedup: {len(merged)} businesses ({len(data) - len(merged)} removed, {n_merged} merged)")

    with open(OUTPUT, "w") as f:
        json.dump(merged, f, indent=2, default=str)
    print(f"Saved to {OUTPUT}")


if __name__ == "__main__":
    dedup()
