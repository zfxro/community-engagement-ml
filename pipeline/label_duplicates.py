"""
Interactive CLI for labeling candidate duplicate pairs.

Presents each pair side-by-side and prompts for:
  1 = same business (will merge)
  0 = different businesses
  s = skip, q = quit

Usage: python3 label_duplicates.py [pairs_csv]
"""

import pandas as pd
import sys

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "review_duplicates.csv"

df = pd.read_csv(CSV_PATH)
df["is_duplicate"] = df["is_duplicate"].astype(object)

remaining = df[df["is_duplicate"].isna() | (df["is_duplicate"].astype(str).isin(["", " ", "nan"]))]
labeled_count = len(df) - len(remaining)

if len(remaining) == 0:
    print("All pairs labeled!")
    sys.exit(0)

print(f"\n{len(remaining)} to label ({labeled_count} done)")
print('  1 = same business (will merge)\n'
      '  0 = different businesses\n'
      '  s = skip, q = quit\n')

n = 1
for idx, row in remaining.iterrows():
    print(f"\n{'='*65}")
    print(f"  Pair {labeled_count + n}/{len(df)}")
    print(f"{'='*65}")
    print(f"\n  A: {row['a_title']}")
    print(f"     Address: {row.get('a_full_address', row['street'])}")
    print(f"     Phone: {row['a_phone']}")
    print(f"     Category: {row['a_category']}")
    print(f"     Reviews: {row['a_reviews']}  Rating: {row['a_rating']}")
    print(f"\n  B: {row['b_title']}")
    print(f"     Address: {row.get('b_full_address', row['street'])}")
    print(f"     Phone: {row['b_phone']}")
    print(f"     Category: {row['b_category']}")
    print(f"     Reviews: {row['b_reviews']}  Rating: {row['b_rating']}")
    print(f"\n  Name score: {row['name_score']}  Phone match: {row['phone_match']}")

    while True:
        ans = input("\n  Same business? (1/0/s/q): ").strip().lower()
        if ans in ("1", "0", "s", "q"):
            break
        print("  Invalid")

    if ans == "q":
        print("\n  Saving...")
        break
    elif ans == "s":
        n += 1
        continue
    else:
        df.at[idx, "is_duplicate"] = str(ans)
        n += 1

df.to_csv(CSV_PATH, index=False)
done = len(df[df["is_duplicate"].astype(str).isin(["1", "0"])])
total = len(df)
print(f"\nSaved. {done}/{total} labeled ({done/total*100:.1f}%)")
