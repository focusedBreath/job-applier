import shutil
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from src.api.deps import get_config
from src.config import Config
from src.resume.models import ResumeData
from src.resume.parser import load_overrides, parse_docx, save_overrides

log = structlog.get_logger()

router = APIRouter(prefix="/resume", tags=["resume"])


class FieldOverrides(BaseModel):
    overrides: dict


@router.post("/upload", response_model=ResumeData)
async def upload_resume(
    file: UploadFile,
    config: Config = Depends(get_config),
) -> ResumeData:
    if not file.filename or not file.filename.endswith(".docx"):
        raise HTTPException(400, "Only .docx files are accepted")

    dest = Path(config.resume_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    log.info("resume.uploaded", path=str(dest))

    try:
        parsed = parse_docx(dest)
    except Exception as e:
        raise HTTPException(422, f"Failed to parse DOCX: {e}") from e

    overrides = load_overrides(config.resume_overrides_path)
    return parsed.merged(overrides)


@router.get("", response_model=ResumeData)
async def get_resume(config: Config = Depends(get_config)) -> ResumeData:
    p = Path(config.resume_path)
    if not p.exists():
        raise HTTPException(404, "No resume uploaded yet")
    try:
        parsed = parse_docx(p)
    except Exception as e:
        raise HTTPException(422, f"Failed to parse DOCX: {e}") from e

    overrides = load_overrides(config.resume_overrides_path)
    return parsed.merged(overrides)


@router.patch("/fields", response_model=dict)
async def patch_fields(
    body: FieldOverrides,
    config: Config = Depends(get_config),
) -> dict:
    existing = load_overrides(config.resume_overrides_path)
    existing.update(body.overrides)
    save_overrides(config.resume_overrides_path, existing)
    log.info("resume.overrides_saved", fields=list(body.overrides.keys()))
    return {"ok": True, "saved": list(body.overrides.keys())}
