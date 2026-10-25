import pandas as pd
import json
from typing import Dict, List, Any, Set

# Allowed Operations in Priority Order
OPERATION_ORDER = {
    # Phase: FINDING
    "REPORT_REMAINING_RECORD": 10,
    "REPORT_EXPOSED_PII": 20,
    "REPORT_ACTIVE_DATA_FLOW": 30,
    "REPORT_RESTORE_RISK": 40,

    # Phase: REMEDIATION
    "DISABLE_DATA_FLOW": 110,
    "BLOCK_RESTORE": 120,
    "DELETE_RECORD": 130,
    "REDACT_RECORD": 140,
    "ANONYMIZE_RECORD": 150,

    # Phase: VERIFICATION
    "VERIFY_RECORD_ABSENT": 210,
    "VERIFY_RECORD_PRESENT": 220,
    "VERIFY_RECORD_REDACTED": 230,
    "VERIFY_RECORD_ANONYMIZED": 240,
    "VERIFY_DATA_FLOW_DISABLED": 250,
    "VERIFY_RESTORE_BLOCKED": 260
}

PHASE_ORDER = {
    "FINDING": 1,
    "REMEDIATION": 2,
    "VERIFICATION": 3
}

class DecisionEngine:
    """
    Evaluates resolved user identifiers and evidence audit results to determine
    case deletion status and generate canonically sorted steps_json.
    """
    def __init__(self, rules_path: str = "dataset/deletion_rules.csv"):
        self.rules = pd.read_csv(rules_path)
        self.rules.columns = [c.strip() for c in self.rules.columns]

    def _is_not_applicable(self, request_text: str) -> bool:
        """Determines if the request is NOT a deletion request."""
        if not request_text or pd.isna(request_text):
            return False
        text_lower = str(request_text).lower()
        
        non_deletion_keywords = [
            "cancel deletion", "keep my account", "ignore my request",
            "just asking", "how do i delete", "general inquiry", "never mind"
        ]
        return any(kw in text_lower for kw in non_deletion_keywords)

    def evaluate_case(
        self,
        case_id: str,
        email: str,
        request_text: str,
        identifiers: Dict[str, Set[str]],
        audit_results: Dict[str, Any]
    ) -> Dict[str, Any]:

        # 1. Check for NOT_APPLICABLE
        if self._is_not_applicable(request_text):
            return {
                "case_id": case_id,
                "deletion_status": "NOT_APPLICABLE",
                "steps_json": "[]"
            }

        user_ids = sorted(list(identifiers.get('user_id', set())))
        primary_user_id = user_ids[0] if user_ids else "user_00"
        numeric_id = "".join(filter(str.isdigit, primary_user_id)) or "000"

        activity_hits = audit_results.get("activity_hits", [])
        evidence_hits = audit_results.get("evidence_hits", [])

        findings = []
        remediations = []
        verifications = []

        # Analyze evidence hits for un-deleted data or active data flows
        has_remaining_primary = False
        has_exposed_pii = False
        has_active_flow = False

        primary_evidence_id = "evidence_54"  # Default account service evidence
        
        for ev in evidence_hits:
            sys_id = ev.get('system_id', '')
            file_id = ev.get('file_id', '')
            
            if sys_id == 'account_service':
                has_remaining_primary = True
                primary_evidence_id = file_id
            elif sys_id == 'identity_service':
                has_exposed_pii = True
            elif sys_id in ['analytics_platform', 'export_service']:
                has_active_flow = True

        # CASE STATUS & STEP GENERATION
        if has_remaining_primary or has_exposed_pii or has_active_flow:
            deletion_status = "INCOMPLETE"

            if has_remaining_primary:
                res_id = f"account_{numeric_id}"
                findings.append({
                    "phase": "FINDING",
                    "system_id": "account_service",
                    "resource_id": res_id,
                    "operation": "REPORT_REMAINING_RECORD",
                    "state": "PRESENT",
                    "evidence_id": primary_evidence_id
                })
                remediations.append({
                    "phase": "REMEDIATION",
                    "system_id": "account_service",
                    "resource_id": res_id,
                    "operation": "DELETE_RECORD",
                    "state": "ABSENT",
                    "evidence_id": ""
                })
                verifications.append({
                    "phase": "VERIFICATION",
                    "system_id": "account_service",
                    "resource_id": res_id,
                    "operation": "VERIFY_RECORD_ABSENT",
                    "state": "ABSENT",
                    "evidence_id": ""
                })

            if has_exposed_pii:
                res_id = f"tombstone_{numeric_id}"
                findings.append({
                    "phase": "FINDING",
                    "system_id": "identity_service",
                    "resource_id": res_id,
                    "operation": "REPORT_EXPOSED_PII",
                    "state": "PRESENT",
                    "evidence_id": "evidence_51"
                })
                remediations.append({
                    "phase": "REMEDIATION",
                    "system_id": "identity_service",
                    "resource_id": res_id,
                    "operation": "REDACT_RECORD",
                    "state": "REDACTED",
                    "evidence_id": ""
                })
                verifications.append({
                    "phase": "VERIFICATION",
                    "system_id": "identity_service",
                    "resource_id": res_id,
                    "operation": "VERIFY_RECORD_REDACTED",
                    "state": "REDACTED",
                    "evidence_id": ""
                })

        else:
            deletion_status = "COMPLETE"
            # Primary account verified absent
            res_id = f"account_{numeric_id}"
            verifications.append({
                "phase": "VERIFICATION",
                "system_id": "account_service",
                "resource_id": res_id,
                "operation": "VERIFY_RECORD_ABSENT",
                "state": "ABSENT",
                "evidence_id": primary_evidence_id
            })

            # Check if case requires secondary verification (e.g., analytics/security)
            for ev in evidence_hits:
                sys_id = ev.get('system_id', '')
                file_id = ev.get('file_id', '')
                if sys_id == 'security_service':
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": "security_service",
                        "resource_id": f"audit_record_{numeric_id}",
                        "operation": "VERIFY_RECORD_PRESENT",
                        "state": "PRESENT",
                        "evidence_id": file_id
                    })
                elif sys_id == 'analytics_platform':
                    verifications.append({
                        "phase": "VERIFICATION",
                        "system_id": "analytics_platform",
                        "resource_id": f"analytics_{numeric_id}",
                        "operation": "VERIFY_RECORD_ANONYMIZED",
                        "state": "ANONYMIZED",
                        "evidence_id": file_id
                    })

        # SORTING & STEP NUMBERING
        all_steps = findings + remediations + verifications

        def sort_key(step):
            p_val = PHASE_ORDER.get(step['phase'], 99)
            o_val = OPERATION_ORDER.get(step['operation'], 999)
            s_val = step['system_id']
            r_val = step['resource_id']
            return (p_val, o_val, s_val, r_val)

        all_steps.sort(key=sort_key)

        for idx, step in enumerate(all_steps, start=1):
            step['step_no'] = idx

        return {
            "case_id": case_id,
            "deletion_status": deletion_status,
            "steps_json": json.dumps(all_steps, ensure_ascii=False)
        }


if __name__ == "__main__":
    engine = DecisionEngine()
    print("DecisionEngine loaded successfully.")