from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models
from ..database import DATA_DIR, get_db
from ..security import get_current_user

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    document = db.get(models.Document, document_id)
    if document is None or not document.file_path:
        raise HTTPException(status_code=404, detail="Document not found")
    path = Path(document.file_path).resolve()
    docs_root = (DATA_DIR / "docs").resolve()
    if docs_root not in path.parents:
        raise HTTPException(status_code=400, detail="Invalid document path")
    if not path.exists():
        raise HTTPException(status_code=404, detail="File is missing on the server")
    return FileResponse(str(path), filename=document.file_name or path.name)
