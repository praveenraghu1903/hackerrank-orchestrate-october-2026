import os
import json
import sqlite3
import re
import pandas as pd
from typing import Dict, Set, List, Any

def normalize_phone(phone: str) -> str:
    """Strips all non-digit characters for robust matching."""
    if not phone or pd.isna(phone):
        return ""
    return re.sub(r'\D', '', str(phone))

class EvidenceAuditor:
    """
    Advanced evidence auditor supporting text, JSON, and SQLite database scanning
    with normalized phone & email matching.
    """
    def __init__(
        self,
        activity_path: str = "dataset/system_activity.csv",
        evidence_manifest_path: str = "dataset/evidence_files.csv"
    ):
        self.system_activity = pd.read_csv(activity_path)
        self.evidence_manifest = pd.read_csv(evidence_manifest_path)

        # Strip whitespace and UTF-8 BOM
        self.system_activity.columns = [c.strip().lstrip('\ufeff') for c in self.system_activity.columns]
        self.evidence_manifest.columns = [c.strip().lstrip('\ufeff') for c in self.evidence_manifest.columns]

        # Identify time columns
        self.act_time_col = next((c for c in ['timestamp', 'time', 'created_at'] if c in self.system_activity.columns), None)
        if self.act_time_col:
            self.system_activity[self.act_time_col] = pd.to_datetime(self.system_activity[self.act_time_col], errors='coerce')

        self.ev_time_col = next((c for c in ['created_at', 'timestamp', 'time'] if c in self.evidence_manifest.columns), None)
        if self.ev_time_col:
            self.evidence_manifest[self.ev_time_col] = pd.to_datetime(self.evidence_manifest[self.ev_time_col], errors='coerce')

    def _search_sqlite(self, db_path: str, search_terms: List[str]) -> List[str]:
        """Scans all tables and columns in a SQLite database file."""
        matched_terms = []
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [r[0] for r in cursor.fetchall()]

            for table in tables:
                cursor.execute(f"PRAGMA table_info({table});")
                cols = [c[1] for c in cursor.fetchall()]
                if not cols:
                    continue
                
                # Query table rows
                cursor.execute(f"SELECT * FROM {table}")
                rows = cursor.fetchall()
                for row in rows:
                    row_str = " ".join([str(val) for val in row if val is not None]).lower()
                    row_digits = re.sub(r'\D', '', row_str)
                    
                    for term in search_terms:
                        term_clean = term.lower()
                        term_digits = re.sub(r'\D', '', term_clean)
                        
                        if term_clean in row_str or (len(term_digits) >= 7 and term_digits in row_digits):
                            if term not in matched_terms:
                                matched_terms.append(term)
            conn.close()
        except Exception:
            pass
        return matched_terms

    def audit_case(self, identifiers: Dict[str, Set[str]], audit_at: str) -> Dict[str, Any]:
        try:
            audit_cutoff = pd.to_datetime(audit_at)
        except Exception:
            audit_cutoff = None

        user_ids = {str(u) for u in identifiers.get('user_id', set()) if u}
        emails = {str(e).lower() for e in identifiers.get('emails', set()) if e}
        phones = {str(p) for p in identifiers.get('phones', set()) if p}
        names = {str(n) for n in identifiers.get('names', set()) if n}
        hashes = {str(h) for h in identifiers.get('email_hashes', set()) if h}

        raw_search_terms = list(user_ids | emails | phones | names | hashes)
        
        activity_hits = []
        evidence_hits = []

        # 1. Scan system_activity.csv
        valid_activities = self.system_activity
        if self.act_time_col and audit_cutoff is not None:
            valid_activities = self.system_activity[self.system_activity[self.act_time_col] <= audit_cutoff]

        for _, row in valid_activities.iterrows():
            row_str = " ".join([str(v) for v in row.values if pd.notna(v)]).lower()
            row_uid = str(row.get('user_id', ''))

            match = False
            if row_uid in user_ids:
                match = True
            else:
                for term in raw_search_terms:
                    if term and term.lower() in row_str:
                        match = True
                        break

            if match:
                activity_hits.append({
                    "activity_id": str(row.get('activity_id', '')),
                    "timestamp": str(row.get(self.act_time_col, '')) if self.act_time_col else '',
                    "system_id": str(row.get('system_id', '')),
                    "operation": str(row.get('operation', '')),
                    "user_id": row_uid,
                    "status": str(row.get('status', ''))
                })

        # 2. Scan evidence files
        valid_evidence = self.evidence_manifest
        if self.ev_time_col and audit_cutoff is not None:
            valid_evidence = self.evidence_manifest[self.evidence_manifest[self.ev_time_col] <= audit_cutoff]

        for _, row in valid_evidence.iterrows():
            file_id = str(row.get('file_id', ''))
            file_path_rel = str(row.get('file_path', ''))
            system_id = str(row.get('system_id', ''))
            file_type = str(row.get('file_type', '')).lower()

            candidate_paths = [
                os.path.join("dataset", file_path_rel),
                file_path_rel,
                os.path.join("dataset", "evidence", os.path.basename(file_path_rel))
            ]

            full_path = next((p for p in candidate_paths if os.path.exists(p)), None)

            if full_path:
                matched_terms = []
                if file_path_rel.endswith(('.db', '.sqlite', '.sqlite3')):
                    matched_terms = self._search_sqlite(full_path, raw_search_terms)
                else:
                    try:
                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read().lower()
                            content_digits = re.sub(r'\D', '', content)
                            
                            for term in raw_search_terms:
                                term_clean = term.lower()
                                term_digits = re.sub(r'\D', '', term_clean)
                                
                                if term_clean in content or (len(term_digits) >= 7 and term_digits in content_digits):
                                    matched_terms.append(term)
                    except Exception:
                        pass

                if matched_terms:
                    evidence_hits.append({
                        "file_id": file_id,
                        "system_id": system_id,
                        "file_type": file_type,
                        "file_path": file_path_rel,
                        "matched_terms": matched_terms
                    })

        return {
            "activity_hits": activity_hits,
            "evidence_hits": evidence_hits
        }


if __name__ == "__main__":
    from code.identity_resolver import IdentityResolver

    resolver = IdentityResolver()
    auditor = EvidenceAuditor()

    sample_requests = pd.read_csv("dataset/sample_deletion_requests.csv")
    
    print("=== Testing EvidenceAuditor on First 5 Sample Cases ===")
    for idx in range(min(5, len(sample_requests))):
        case = sample_requests.iloc[idx]
        resolved_ids = resolver.resolve_identifiers(case['email'], case['audit_at'])
        audit_res = auditor.audit_case(resolved_ids, case['audit_at'])

        print(f"\nCase: {case['case_id']} | Email: {case['email']}")
        print(f"  Activity Hits: {len(audit_res['activity_hits'])}")
        print(f"  Evidence Hits: {len(audit_res['evidence_hits'])}")