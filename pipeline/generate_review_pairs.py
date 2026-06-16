"""
Generate candidate match pairs between business data and proxy/outcome records.

Two matching passes:
1. Exact phone match
2. Fuzzy name match (weighted ratio >= 70)

Outputs CSVs for manual labeling via label_pairs.py.
"""

import json, os, re, html
import pandas as pd
from rapidfuzz import fuzz, process as fuzz_process

PROXY_CSV = os.environ.get("PROXY_CSV", "proxy_members.csv")
DEFINITIVE_JSON = os.environ.get("DEFINITIVE_JSON", "business_data_deduped.json")
OUTCOME_XLSX = os.environ.get("OUTCOME_XLSX", "outcome_records.xlsx")


def normalize_phone(p):
    if not p or pd.isna(p):
        return ""
    digits = re.sub(r"\D", "", str(p))
    if len(digits) == 10:
        return digits
    if len(digits) == 11 and digits[0] == "1":
        return digits[1:]
    return ""


def parse_street(addr_str):
    if not addr_str or pd.isna(addr_str):
        return ""
    s = str(addr_str).lower().strip()
    s = re.sub(r",.*", "", s)
    s = re.sub(r"\b(ny)\b", "", s).strip()
    s = re.sub(r"[.,#]", "", s).strip()
    return s


def parse_street_gmaps(comp_addr):
    if isinstance(comp_addr, dict):
        return str(comp_addr.get("street", "")).lower().strip()
    return ""


def load_gmaps():
    with open(DEFINITIVE_JSON) as f:
        return pd.DataFrame(json.load(f))


def generate_proxy_pairs(gmaps_df):
    """Pass 1: phone-match. Pass 2: strong name match for unmatched only."""
    proxy_src = pd.read_csv(PROXY_CSV)
    for c in ["name", "address", "category"]:
        if c in proxy_src.columns:
            proxy_src[c] = proxy_src[c].apply(lambda x: html.unescape(str(x)) if pd.notna(x) else x)

    gmaps_df = gmaps_df.copy()
    gmaps_df["phone_norm"] = gmaps_df["phone"].apply(normalize_phone)
    gmaps_df["street_parsed"] = gmaps_df["complete_address"].apply(parse_street_gmaps)
    gmaps_df["name_clean"] = gmaps_df["title"].str.lower().str.strip()

    rows = []

    # Pass 1: phone match
    gmap_by_phone = {}
    for gi, gr in gmaps_df.iterrows():
        p = gr["phone_norm"]
        if p:
            gmap_by_phone.setdefault(p, []).append(gi)

    phone_matched_proxy = set()

    for pi, pr in proxy_src.iterrows():
        p_phone = normalize_phone(pr.get("phone", ""))
        if not p_phone:
            continue
        gis = gmap_by_phone.get(p_phone, [])
        for gi in gis:
            gr = gmaps_df.iloc[gi]
            rows.append(_proxy_row(pr, gr, 0, 0, 1.0, 1.0))
            phone_matched_proxy.add(pi)

    # Pass 2: strong name match for unmatched
    gmap_names = gmaps_df["name_clean"].tolist()
    gmap_indices = gmaps_df.index.tolist()

    for pi, pr in proxy_src.iterrows():
        if pi in phone_matched_proxy:
            continue
        p_name = str(pr.get("name", "")).lower().strip()
        if not p_name:
            continue

        # Only take matches >= 90%
        m = fuzz_process.extractOne(p_name, gmap_names, scorer=fuzz.WRatio, score_cutoff=90)
        if m:
            matched_name, n_score, gi = m
            gr = gmaps_df.iloc[gi]
            rows.append(_proxy_row(pr, gr, 0, n_score / 100.0, 0, n_score / 100.0))

    df = pd.DataFrame(rows)
    if len(df) > 0:
        df = df.sort_values("combined_score", ascending=False)
    df.to_csv("review_proxy_pairs.csv", index=False)
    print(f"  Proxy: {len(df)} candidate pairs ({len(phone_matched_proxy)} phone, {len(df) - len(phone_matched_proxy)} name)")
    return df


def _proxy_row(pr, gr, a_score, n_score, p_score, combined):
    return {
        "proxy_name": pr.get("name", ""),
        "proxy_phone": pr.get("phone", ""),
        "proxy_address": pr.get("address", ""),
        "proxy_category": pr.get("category", ""),
        "gmaps_title": gr["title"],
        "gmaps_phone": gr.get("phone", ""),
        "gmaps_street": gr.get("street_parsed", ""),
        "gmaps_category": gr.get("category", ""),
        "address_score": round(a_score, 3),
        "name_score": round(n_score, 3),
        "phone_score": round(p_score, 3),
        "combined_score": round(combined, 3),
        "is_match": "",
    }


def generate_outcome_pairs(gmaps_df, top_k=5):
    import openpyxl
    wb = openpyxl.load_workbook(OUTCOME_XLSX, data_only=True)
    ws = wb.active
    records = []
    for row in ws.iter_rows(min_row=3, values_only=True):
        name = row[0]
        if not name or not str(name).strip():
            continue
        records.append({
            "name": str(name).strip(),
            "phone": normalize_phone(row[2]) if row[2] else "",
        })

    gmaps_df = gmaps_df.copy()
    gmaps_df["phone_norm"] = gmaps_df["phone"].apply(normalize_phone)
    gmaps_df["name_clean"] = gmaps_df["title"].str.lower().str.strip()
    gmap_names = gmaps_df["name_clean"].tolist()
    gmap_by_phone = {}
    for gi, gr in gmaps_df.iterrows():
        p = gr["phone_norm"]
        if p:
            gmap_by_phone.setdefault(p, []).append(gi)

    rows = []
    phone_matched = set()

    # Pass 1: phone
    for si, s in enumerate(records):
        if not s["phone"]:
            continue
        gis = gmap_by_phone.get(s["phone"], [])
        for gi in gis:
            gr = gmaps_df.iloc[gi]
            rows.append({
                "outcome_name": s["name"],
                "outcome_phone": s["phone"],
                "gmaps_title": gr["title"],
                "gmaps_phone": gr.get("phone", ""),
                "gmaps_address": gr.get("address", ""),
                "gmaps_category": gr.get("category", ""),
                "name_score": 1.0,
                "phone_score": 1.0,
                "combined_score": 1.0,
                "is_match": "",
            })
            phone_matched.add(si)

    # Pass 2: name match for unmatched
    for si, s in enumerate(records):
        if si in phone_matched:
            continue
        s_name = s["name"].lower().strip()
        m = fuzz_process.extractOne(s_name, gmap_names, scorer=fuzz.WRatio, score_cutoff=75)
        if m:
            matched_name, n_score, gi = m
            gr = gmaps_df.iloc[gi]
            p_score = 1.0 if (gr["phone_norm"] and s["phone"] and gr["phone_norm"] == s["phone"]) else 0.0
            combined = n_score / 100.0 * 0.60 + p_score * 0.40
            rows.append({
                "outcome_name": s["name"],
                "outcome_phone": s["phone"],
                "gmaps_title": gr["title"],
                "gmaps_phone": gr.get("phone", ""),
                "gmaps_address": gr.get("address", ""),
                "gmaps_category": gr.get("category", ""),
                "name_score": round(n_score / 100.0, 3),
                "phone_score": round(p_score, 3),
                "combined_score": round(combined, 3),
                "is_match": "",
            })

    df = pd.DataFrame(rows)
    if len(df) > 0:
        df = df.sort_values("combined_score", ascending=False)
    df.to_csv("review_outcome_pairs.csv", index=False)
    print(f"  Outcome records: {len(df)} candidate pairs")
    return df


if __name__ == "__main__":
    print("Loading GMaps data...")
    gmaps = load_gmaps()
    print(f"  {len(gmaps)} businesses")

    print("\nGenerating proxy ↔ GMaps review pairs...")
    generate_proxy_pairs(gmaps)

    print("\nGenerating outcome ↔ GMaps review pairs...")
    generate_outcome_pairs(gmaps)
