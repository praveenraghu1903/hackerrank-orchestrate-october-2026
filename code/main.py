import os
import sys
import json
import pandas as pd

# Automatically locate project root (parent directory of code/)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from identity_resolver import IdentityResolver
from evidence_auditor import EvidenceAuditor
from decision_engine import DecisionEngine

def resolve_path(rel_path: str) -> str:
    """Helper to resolve paths relative to project root."""
    if os.path.isabs(rel_path):
        return rel_path
    return os.path.join(PROJECT_ROOT, rel_path)

def run_pipeline(
    requests_rel_path: str = "dataset/deletion_requests.csv",
    output_rel_path: str = "output.csv"
):
    requests_path = resolve_path(requests_rel_path)
    output_path = resolve_path(output_rel_path)

    print(f"=== Running Audit Pipeline ===")
    print(f"Reading requests from: {requests_path}")

    resolver = IdentityResolver(
        identities_path=resolve_path("dataset/user_identities.csv"),
        audit_log_path=resolve_path("dataset/user_audit_log.csv")
    )
    auditor = EvidenceAuditor(
        activity_path=resolve_path("dataset/system_activity.csv"),
        evidence_manifest_path=resolve_path("dataset/evidence_files.csv")
    )
    engine = DecisionEngine(
        rules_path=resolve_path("dataset/deletion_rules.csv")
    )

    requests_df = pd.read_csv(requests_path)
    requests_df.columns = [c.strip().lstrip('\ufeff') for c in requests_df.columns]

    results = []

    for idx, row in requests_df.iterrows():
        case_id = str(row['case_id'])
        email = str(row['email'])
        audit_at = str(row['audit_at'])
        request_text = str(row.get('request_text', ''))

        # 1. Resolve Identifiers
        identifiers = resolver.resolve_identifiers(email, audit_at)

        # 2. Audit Evidence & System Activity
        audit_res = auditor.audit_case(identifiers, audit_at)

        # 3. Decision Engine & Steps Generator
        case_output = engine.evaluate_case(case_id, email, request_text, identifiers, audit_res)
        results.append(case_output)

    out_df = pd.DataFrame(results)
    out_df.to_csv(output_path, index=False)
    print(f"\nSuccessfully generated {output_path} with {len(out_df)} rows.")

    # Run evaluation if testing on sample dataset
    sample_gt = resolve_path("dataset/sample_output.csv")
    if "sample" in requests_rel_path and os.path.exists(sample_gt):
        evaluate_sample_results(output_path, sample_gt)

def evaluate_sample_results(predicted_path: str, ground_truth_path: str):
    pred_df = pd.read_csv(predicted_path)
    gt_df = pd.read_csv(ground_truth_path)

    merged = pd.merge(pred_df, gt_df, on="case_id", suffixes=('_pred', '_gt'))
    status_matches = (merged['deletion_status_pred'] == merged['deletion_status_gt']).sum()
    total = len(merged)
    accuracy = (status_matches / total) * 100

    print(f"\n================ EVALUATION REPORT ================")
    print(f"Case Deletion Status Accuracy: {status_matches}/{total} ({accuracy:.2f}%)")
    print("===================================================")

if __name__ == "__main__":
    # Process full dataset (518 cases) into output.csv
    run_pipeline("dataset/deletion_requests.csv", "output.csv")