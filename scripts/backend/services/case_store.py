import os
import uuid
import yaml
from datetime import datetime
from typing import Optional, Dict, List

CASES_DIR = os.environ.get("ACADEMIC_DETECTIVE_CASES_DIR", "./cases")


class CaseStore:
    def __init__(self):
        self._cases: Dict[str, dict] = {}

    def _generate_id(self, name: str) -> str:
        prefix = "".join([c for c in name[:3].upper() if c.isalnum()])
        date_str = datetime.now().strftime("%Y%m%d")
        rand = uuid.uuid4().hex[:6].upper()
        return f"{prefix}-{date_str}-{rand}"

    def _find_existing_dir(self, scholar_name: str, institution: str) -> Optional[str]:
        for entry in os.listdir(CASES_DIR):
            full = os.path.join(CASES_DIR, entry)
            if not os.path.isdir(full):
                continue
            if scholar_name in entry and institution in entry:
                return full
        return None

    def create(self, scholar_name: str, institution: str = "") -> dict:
        existing = self._find_existing_dir(scholar_name, institution)
        if existing:
            case_dir = existing
        else:
            folder_name = f"{scholar_name}_{institution}" if institution else scholar_name
            case_dir = os.path.join(CASES_DIR, folder_name)
            os.makedirs(case_dir, exist_ok=True)
            os.makedirs(os.path.join(case_dir, "data"), exist_ok=True)
            os.makedirs(os.path.join(case_dir, "pdfs"), exist_ok=True)
            os.makedirs(os.path.join(case_dir, "screenshots"), exist_ok=True)
            os.makedirs(os.path.join(case_dir, "reports"), exist_ok=True)

        case_id = self._generate_id(scholar_name)
        case = {
            "case_id": case_id,
            "scholar_name": scholar_name,
            "institution": institution,
            "case_dir": case_dir,
            "phase": "init",
            "messages": [],
            "tracked_evidence": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self._cases[case_id] = case
        return case

    def get(self, case_id: str) -> Optional[dict]:
        return self._cases.get(case_id)

    def list_all(self) -> List[dict]:
        return list(self._cases.values())

    def delete(self, case_id: str) -> bool:
        if case_id in self._cases:
            del self._cases[case_id]
            return True
        return False

    def add_message(self, case_id: str, role: str, content: str):
        case = self._cases.get(case_id)
        if case:
            case["messages"].append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
            })
            case["updated_at"] = datetime.now().isoformat()

    def update_phase(self, case_id: str, phase: str):
        case = self._cases.get(case_id)
        if case:
            case["phase"] = phase
            case["updated_at"] = datetime.now().isoformat()

    def get_messages(self, case_id: str) -> List[dict]:
        case = self._cases.get(case_id)
        return case["messages"] if case else []


store = CaseStore()
