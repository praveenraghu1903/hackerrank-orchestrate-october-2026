# Ghost Data Still Exists - AI Deletion Audit Agent

An automated privacy audit agent built for Northstar Shop to audit user deletion requests, trace historical user identities across distributed stores, detect un-redacted PII and active sync data flows, and generate canonical remediation/verification steps.

## Architecture & Approach Overview

The solution consists of four deterministic modules:

1. **Identity Resolution (`identity_resolver.py`)**
   - Maps requested emails to `user_id`s in `user_identities.csv`.
   - Traces historical email, phone number, name, and email hash changes in `user_audit_log.csv` up to `audit_at`.

2. **Evidence & Activity Audit (`evidence_auditor.py`)**
   - Scans `system_activity.csv` for logged operations and active data sync/export tasks.
   - Inspects JSON logs, text files, and SQLite databases (`.db`/`.sqlite`) in `dataset/evidence/` using digit-only phone normalization and full schema reflection.

3. **Decision & Remediation Engine (`decision_engine.py`)**
   - Cross-references findings against `deletion_rules.csv`.
   - Classifies case status into `COMPLETE`, `INCOMPLETE`, or `NOT_APPLICABLE`.
   - Generates and canonically orders `steps_json` by Phase (`FINDING` -> `REMEDIATION` -> `VERIFICATION`), Operation Priority Index, `system_id`, and `resource_id`.

4. **Pipeline Execution & Evaluation (`main.py`)**
   - Audits all 518 cases in `dataset/deletion_requests.csv` and produces the 519-line `output.csv`.

---

## Setup & Execution Instructions

### Prerequisites
- Python 3.9+
- `pandas` library

```bash
pip install pandas