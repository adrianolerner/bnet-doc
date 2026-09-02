from typing import Generator
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import verify_token
from app.schemas.auth import TokenData

# O endpoint onde o cliente realiza o login (usado pelo OpenAPI Swagger UI)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def get_db() -> Generator:
    """
    Fornece conexões isoladas ao banco de dados por requisição.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, token: str = Depends(oauth2_scheme)) -> TokenData:
    """
    Valida o JWT recebido nas requisições HTTP e injeta o objeto de dados do usuário autenticado.
    Retorna HTTPException (401) caso o token seja inválido ou expirado.
    """
    if not token:
        # Fallback para ambientes restritos onde proxies (como Nginx Proxy Manager)
        # removem o cabeçalho 'Authorization'.
        token = request.headers.get("X-API-Token")
        
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciais inválidas ou token expirado.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token_data = verify_token(token)
    if token_data is None:
        raise credentials_exception
        
    return token_data
