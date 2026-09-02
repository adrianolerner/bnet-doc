from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.core.security import authenticate_ldap, create_access_token
from app.schemas.auth import Token, UserLogin, TokenData
from app.core.rate_limit import limiter

router = APIRouter()

@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Endpoint de Autenticação compatível com OAuth2. 
    Realiza o login com usuário/senha contra o LDAP Active Directory.
    Exige o formato Form URL-Encoded (compatível com botão Authorize do Swagger).
    """
    user_info = authenticate_ldap(form_data.username, form_data.password)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nome de usuário/senha incorretos ou você não pertence ao grupo de TI exigido.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Gera o JWT Token salvando o nome de usuário (sub). Evitamos salvar todos os grupos do AD no token para não exceder o limite de tamanho de cabeçalho HTTP em proxies (ex: Nginx).
    access_token = create_access_token(
        data={"sub": user_info["username"], "groups": []}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login-json", response_model=Token)
@limiter.limit("5/minute")
def login_json_payload(
    request: Request,
    credentials: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Endpoint alternativo para login enviando payload JSON direto (útil para integrações JSON de API).
    """
    user_info = authenticate_ldap(credentials.username, credentials.password)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nome de usuário/senha incorretos ou você não pertence ao grupo de TI exigido.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Gera o JWT Token salvando o nome de usuário (sub). Evitamos salvar todos os grupos do AD no token para não exceder o limite de tamanho de cabeçalho HTTP em proxies (ex: Nginx).
    access_token = create_access_token(
        data={"sub": user_info["username"], "groups": []}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/refresh", response_model=Token)
@limiter.limit("5/minute")
def refresh_token(
    request: Request,
    current_user: TokenData = Depends(get_current_user)
):
    """
    Endpoint para renovar a sessão do usuário com base num token ainda válido.
    """
    access_token = create_access_token(
        data={"sub": current_user.username, "groups": current_user.groups}
    )
    return {"access_token": access_token, "token_type": "bearer"}
