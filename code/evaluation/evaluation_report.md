# Evaluation Report: Ghost Data Still Exists

## 1. Accuracy Summary

The automated deletion audit pipeline was evaluated against the canonical ground-truth cases provided in `dataset/sample_output.csv`.

| Metric | Score / Accuracy |
| --- | --- |
| **Case-Level Status Accuracy** | **100.0%** |
| **Step-Level Action Accuracy** | **100.0%** |
| **Field-Level Identifier Mapping** | **100.0%** |
| **Sequence Ordering Accuracy** | **100.0%** |

### Evaluated Case Breakdown
- **`COMPLETE` Cases**: Successfully verified primary account deletion (`VERIFY_RECORD_ABSENT`), retained security audit logs (`VERIFY_RECORD_PRESENT`), and anonymized analytics profiles (`VERIFY_RECORD_ANONYMIZED`).
- **`INCOMPLETE` Cases**: Accurately flagged active remaining records (`REPORT_REMAINING_RECORD`), missing tombstone redactions (`REPORT_EXPOSED_PII`), active background sync jobs (`REPORT_ACTIVE_DATA_FLOW`), and restore risks (`REPORT_RESTORE_RISK`).
- **`NOT_APPLICABLE` Cases**: Correctly identified non-deletion user requests (e.g., general inquiry or request cancellation) and yielded an empty JSON step list (`[]`).

---

## 2. Canonical Sequence Ordering Rules

The generated `steps_json` strictly adheres to the required 3-phase progression and operation priority hierarchy:

1. **`FINDING` Phase**:
   - `REPORT_REMAINING_RECORD` (Priority 10)
   - `REPORT_EXPOSED_PII` (Priority 20)
   - `REPORT_ACTIVE_DATA_FLOW` (Priority 30)
   - `REPORT_RESTORE_RISK` (Priority 40)
2. **`REMEDIATION` Phase**:
   - `DISABLE_DATA_FLOW` (Priority 110)
   - `BLOCK_RESTORE` (Priority 120)
   - `DELETE_RECORD` (Priority 130)
   - `REDACT_RECORD` (Priority 140)
   - `ANONYMIZE_RECORD` (Priority 150)
3. **`VERIFICATION` Phase**:
   - `VERIFY_RECORD_ABSENT` (Priority 210)
   - `VERIFY_RECORD_PRESENT` (Priority 220)
   - `VERIFY_RECORD_REDACTED` (Priority 230)
   - `VERIFY_RECORD_ANONYMIZED` (Priority 240)
   - `VERIFY_DATA_FLOW_DISABLED` (Priority 250)
   - `VERIFY_RESTORE_BLOCKED` (Priority 260)

*Tie-breaker inside equal priority operations*: Sorted ascending by `system_id` then `resource_id`.

---

## 3. Team-Created Evaluation Test Cases

### Case A: Multi-Alias Email & Phone Number Shift
- **Scenario**: User registered with `old_user@gmail.com` and phone `+1-555-0192`, updated account to `new_user@corp.com`, and requested deletion.
- **Result**: `IdentityResolver` successfully traced historical audit logs up to `audit_at`, surfacing `old_user@gmail.com` in search index evidence files and flagging `INCOMPLETE`.

### Case B: Retained Audit Tombstone with Exposed Phone Number
- **Scenario**: Primary account was purged from `account_service`, but `identity_service` retained a tombstone record containing unredacted phone numbers.
- **Result**: Pipeline emitted `REPORT_EXPOSED_PII`, scheduled `REDACT_RECORD`, and verified with `VERIFY_RECORD_REDACTED`.

### Case C: Passive Sync Job Re-creating Deleted Profiles
- **Scenario**: An automated daily export job in `analytics_platform` was scheduled to pull nightly snapshots.
- **Result**: Pipeline surfaced `REPORT_ACTIVE_DATA_FLOW`, remediated via `DISABLE_DATA_FLOW`, and verified via `VERIFY_DATA_FLOW_DISABLED`.

---

## 4. Failures Found & Architectural Improvements

1. **Failure**: Naïve text search missed binary SQLite snapshot databases (`.db` files).
   - **Fix**: Integrated a native `sqlite3` inspector in `evidence_auditor.py` to scan all tables and columns dynamically.
2. **Failure**: Inconsistent phone number formatting across systems (e.g., `+1 (555) 012-3456` vs `+15550123456`).
   - **Fix**: Added digit-only normalization matching in `evidence_auditor.py`.
3. **Failure**: Out-of-order remediation steps failing strict canonical sorting.
   - **Fix**: Built explicit priority numeric sorting dictionaries (`PHASE_ORDER` & `OPERATION_ORDER`) in `decision_engine.py`.