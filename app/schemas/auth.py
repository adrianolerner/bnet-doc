from typing import List, Optional
from pydantic import BaseModel, Field

class UserLogin(BaseModel):
    username: str = Field(..., description="Nome de usuário do Active Directory (sAMAccountName)")
    password: str = Field(..., description="Senha do usuário do AD")

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    groups: List[str] = []

class UserOut(BaseModel):
    username: str
    name: Optional[str] = None
    email: Optional[str] = None
    groups: List[str] = []
