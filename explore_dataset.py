# explore_dataset.py
import csv
import json
import pandas as pd

print("=== 1. SAMPLE DELETION REQUESTS ===")
df_req = pd.read_csv("dataset/sample_deletion_requests.csv")
print(df_req.head())

print("\n=== 2. DELETION RULES ===")
df_rules = pd.read_csv("dataset/deletion_rules.csv")
print(df_rules)

print("\n=== 3. SAMPLE OUTPUT GROUND TRUTH ===")
df_out = pd.read_csv("dataset/sample_output.csv")
for idx, row in df_out.iterrows():
    print(f"\nCase ID: {row['case_id']} | Status: {row['deletion_status']}")
    steps = json.loads(row['steps_json'])
    print(f"Total Steps: {len(steps)}")
    if steps:
        print("First Step:", steps[0])
