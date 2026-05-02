import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from services.case_store import store

router = APIRouter(prefix="/api/cases", tags=["upload"])

FILE_TYPES = {
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".xlsx": "excel",
    ".csv": "excel",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
}


@router.post("/{case_id}/upload")
async def upload_file(case_id: str, file: UploadFile = File(...)):
    case = store.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    ext = os.path.splitext(file.filename or "")[1].lower()
    file_type = FILE_TYPES.get(ext, "unknown")

    # Determine subdir
    subdirs = {"pdf": "pdfs", "image": "screenshots", "excel": "data", "yaml": "data", "json": "data"}
    subdir = subdirs.get(file_type, "data")
    save_dir = os.path.join(case["case_dir"], subdir)
    os.makedirs(save_dir, exist_ok=True)

    file_id = f"{uuid.uuid4().hex[:8]}{ext}"
    save_path = os.path.join(save_dir, file_id)

    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    return {
        "file_id": file_id,
        "filename": file.filename,
        "type": file_type,
        "saved_path": save_path,
    }
