import pandas as pd
import json

sample_reqs = pd.read_csv("dataset/sample_deletion_requests.csv")
sample_outs = pd.read_csv("dataset/sample_output.csv")

merged = pd.merge(sample_reqs, sample_outs, on="case_id")

for idx, row in merged.head(5).iterrows():
    print(f"=== {row['case_id']} ===")
    print(f"Email: {row['email']}")
    print(f"Request Text: {row['request_text']}")
    print(f"Reported Status: {row['reported_status']}")
    print(f"Ground Truth Status: {row['deletion_status']}")
    steps = json.loads(row['steps_json'])
    print(f"Steps Count: {len(steps)}")
    for s in steps:
        print("  -", s)
    print()