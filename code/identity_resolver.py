import pandas as pd
from typing import Dict, Set

class IdentityResolver:
    """
    Resolves current and historical user identifiers up to a given audit cutoff.
    Traces old emails, phone numbers, names, and email hashes from user_audit_log.csv,
    even if the user was already removed from user_identities.csv.
    """
    def __init__(self, identities_path: str = "dataset/user_identities.csv", audit_log_path: str = "dataset/user_audit_log.csv"):
        self.identities = pd.read_csv(identities_path)
        self.audit_log = pd.read_csv(audit_log_path)
        
        # Clean column names (strip whitespace)
        self.identities.columns = [c.strip() for c in self.identities.columns]
        self.audit_log.columns = [c.strip() for c in self.audit_log.columns]

        # Identify timestamp column in audit_log
        self.time_col = None
        for col in ['timestamp', 'time', 'created_at', 'changed_at', 'updated_at']:
            if col in self.audit_log.columns:
                self.time_col = col
                break
        
        if self.time_col:
            self.audit_log[self.time_col] = pd.to_datetime(self.audit_log[self.time_col], errors='coerce')

    def resolve_identifiers(self, email: str, audit_at: str) -> Dict[str, Set[str]]:
        identifiers = {
            "user_id": set(),
            "emails": set(),
            "phones": set(),
            "names": set(),
            "email_hashes": set()
        }
        
        if pd.isna(email) or not str(email).strip():
            return identifiers

        clean_email = str(email).strip().lower()

        # 1. Check current identities table
        if 'email' in self.identities.columns:
            matched_user = self.identities[self.identities['email'].astype(str).str.lower() == clean_email]
            
            for _, row in matched_user.iterrows():
                uid = str(row['user_id'])
                identifiers['user_id'].add(uid)
                if pd.notna(row.get('email')): identifiers['emails'].add(str(row['email']).lower())
                if pd.notna(row.get('phone')): identifiers['phones'].add(str(row['phone']))
                if pd.notna(row.get('name')): identifiers['names'].add(str(row['name']))
                if pd.notna(row.get('email_hash')): identifiers['email_hashes'].add(str(row['email_hash']))

        # 2. Check audit log for user_ids linked to this email (in old_value or new_value)
        old_col = 'old_value' if 'old_value' in self.audit_log.columns else None
        new_col = 'new_value' if 'new_value' in self.audit_log.columns else None
        
        mask = pd.Series(False, index=self.audit_log.index)
        if old_col:
            mask |= (self.audit_log[old_col].astype(str).str.lower() == clean_email)
        if new_col:
            mask |= (self.audit_log[new_col].astype(str).str.lower() == clean_email)
            
        historical_matches = self.audit_log[mask]
        
        if 'user_id' in historical_matches.columns:
            for uid in historical_matches['user_id'].dropna().unique():
                identifiers['user_id'].add(str(uid))

        # Always add the requested primary email
        identifiers['emails'].add(clean_email)

        # 3. Trace all identity history in audit log up to audit_at for all resolved user_ids
        try:
            audit_cutoff = pd.to_datetime(audit_at)
        except Exception:
            audit_cutoff = None

        for uid in list(identifiers['user_id']):
            uid_mask = (self.audit_log['user_id'].astype(str) == str(uid))
            if self.time_col and audit_cutoff is not None:
                uid_mask &= (self.audit_log[self.time_col] <= audit_cutoff)
                
            user_logs = self.audit_log[uid_mask]
            
            for _, log in user_logs.iterrows():
                field = str(log.get('field_changed', '')).lower()
                old_val = str(log.get(old_col, '')) if old_col and pd.notna(log.get(old_col)) else None
                new_val = str(log.get(new_col, '')) if new_col and pd.notna(log.get(new_col)) else None
                
                target_set = None
                if 'email' in field and 'hash' not in field:
                    target_set = identifiers['emails']
                elif 'phone' in field:
                    target_set = identifiers['phones']
                elif 'name' in field:
                    target_set = identifiers['names']
                elif 'hash' in field:
                    target_set = identifiers['email_hashes']

                if target_set is not None:
                    if old_val and old_val.lower() not in ['nan', 'none', '']:
                        target_set.add(old_val.lower() if 'email' in field else old_val)
                    if new_val and new_val.lower() not in ['nan', 'none', '']:
                        target_set.add(new_val.lower() if 'email' in field else new_val)

        return identifiers

if __name__ == "__main__":
    resolver = IdentityResolver()
    
    # Test with real emails from sample_deletion_requests.csv
    sample_requests = pd.read_csv("dataset/sample_deletion_requests.csv")
    print("=== Testing IdentityResolver on sample requests ===")
    
    for _, req in sample_requests.head(3).iterrows():
        case_id = req['case_id']
        email = req['email']
        audit_at = req['audit_at']
        
        resolved = resolver.resolve_identifiers(email, audit_at)
        print(f"\nCase: {case_id} | Primary Email: {email}")
        for k, v in resolved.items():
            print(f"  {k}: {v}")