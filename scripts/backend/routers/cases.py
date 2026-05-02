from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import List
from services.case_store import store
from models.schemas import CaseCreate, CaseResponse

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.post("")
async def create_case(body: CaseCreate):
    case = store.create(body.scholar_name, body.institution or "")
    return {
        "case_id": case["case_id"],
        "case_dir": case["case_dir"],
        "scholar_name": case["scholar_name"],
        "institution": case["institution"],
        "phase": case["phase"],
        "created_at": case["created_at"],
    }


@router.get("")
async def list_cases() -> List[dict]:
    return store.list_all()


@router.get("/{case_id}")
async def get_case(case_id: str):
    case = store.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@router.delete("/{case_id}")
async def delete_case(case_id: str):
    ok = store.delete(case_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"deleted": True}
