import os
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse

from app.api.deps import get_current_user
from app.schemas.auth import TokenData
from app.core import files as file_manager

router = APIRouter()

@router.post("/upload", status_code=status.HTTP_201_CREATED)
def upload_file(
    file: UploadFile = File(...),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Realiza o upload temporário de um arquivo.
    """
    try:
        temp_path = file_manager.save_temp_file(file)
        return {"file_path": temp_path, "filename": file.filename}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao salvar arquivo: {str(e)}"
        )

@router.get("/download")
def download_file(
    path: str,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Faz o download seguro de um arquivo armazenado.
    """
    # Security: prevent path traversal (e.g. path=../../etc/passwd)
    normalized_path = path.replace("/", os.sep).replace("\\", os.sep)
    abs_path = os.path.abspath(normalized_path)
    upload_abs_path = os.path.abspath(file_manager.UPLOAD_DIR)
    
    if not abs_path.startswith(upload_abs_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Caminho de arquivo inválido."
        )
        
    if not os.path.exists(abs_path) or not os.path.isfile(abs_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo não encontrado."
        )
        
    filename = os.path.basename(abs_path)
    # Using content_disposition_type="inline" so browser preview works, while download is still possible
    return FileResponse(
        path=abs_path,
        filename=filename,
        content_disposition_type="inline"
    )
