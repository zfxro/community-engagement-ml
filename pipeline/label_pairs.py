"""
Interactive CLI for labeling candidate match pairs.

Presents each proxy/outcome-to-business pair and prompts for:
  1 = match (same business)
  0 = not a match
  s = skip, q = quit

Usage: python3 label_pairs.py [pairs_csv]
"""

import pandas as pd
import sys, os

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "review_proxy_pairs.csv"

df = pd.read_csv(CSV_PATH)
if "is_match" in df.columns:
    df["is_match"] = df["is_match"].astype(object)
else:
    df["is_match"] = ""
    df["is_match"] = df["is_match"].astype(object)

# Only keep pairs we haven't labeled yet
remaining = df[df["is_match"].isna() | (df["is_match"].astype(str).isin(["", " ", "nan", "0.0", "1.0"]))]

remaining = remaining.copy()
labeled_count = len(df) - len(remaining)

if len(remaining) == 0:
    print("All pairs already labeled!")
    sys.exit(0)

# Determine pair type from CSV name
pair_type = "PROXY" if "proxy" in CSV_PATH.lower() else "OUTCOME"

print(f"\nLoaded {len(remaining)} unlabeled pairs from {CSV_PATH} ({labeled_count} already done)")
print("Controls: 1 = match, 0 = not a match, s = skip, q = quit (saves progress)\n")

n = 1
for idx, row in remaining.iterrows():
    print(f"\n{'='*60}")
    print(f"  Pair {labeled_count + n}/{len(df)}")
    print(f"{'='*60}")

    if pair_type == "PROXY":
        print(f"\n  PROXY: {row.get('proxy_name', row.get('chamber_name', 'N/A'))}")
        print(f"    Phone:    {row.get('proxy_phone', row.get('chamber_phone', ''))}")
        print(f"    Address:  {row.get('proxy_address', row.get('chamber_address', ''))}")
        print(f"    Category: {row.get('proxy_category', row.get('chamber_category', ''))}")
        print(f"\n  GMAPS:  {row['gmaps_title']}")
        print(f"    Phone:    {row.get('gmaps_phone', '')}")
        print(f"    Street:   {row.get('gmaps_street', '')}")
        print(f"    Category: {row.get('gmaps_category', '')}")
    else:
        print(f"\n  OUTCOME: {row.get('outcome_name', row.get('sponsor_name', 'N/A'))}")
        print(f"    Phone:    {row.get('outcome_phone', row.get('sponsor_phone', ''))}")
        print(f"\n  GMAPS:  {row['gmaps_title']}")
        print(f"    Phone:    {row.get('gmaps_phone', '')}")
        print(f"    Address:  {row.get('gmaps_address', '')}")
        print(f"    Category: {row.get('gmaps_category', '')}")

    print(f"\n  Scores: addr={row.get('address_score', '-')}  name={row['name_score']}  phone={row['phone_score']}  combined={row['combined_score']}")

    while True:
        try:
            ans = input("\n  Match? (1/0/s/q): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = "q"
        if ans in ("1", "0", "s", "q"):
            break
        print("  Invalid. Enter 1, 0, s, or q")

    if ans == "q":
        print("\n  Saving progress...")
        break
    elif ans == "s":
        n += 1
        continue
    else:
        df.at[idx, "is_match"] = str(ans)
        n += 1

df.to_csv(CSV_PATH, index=False)
done = len(df[df["is_match"].astype(str).isin(["1", "0"])])
print(f"\nSaved. {done}/{len(df)} labeled ({done/len(df)*100:.1f}%)")
