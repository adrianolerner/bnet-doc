import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Permite ler variáveis do arquivo .env
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Banco de Dados
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "bnet_doc"
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/bnet_doc"

    # JWT Configurações
    JWT_SECRET_KEY: str = "b2c83d6a9925db59adcb9582d2c18090f45a05b38cfc1b48b99cfc1a5db4e3d0"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # LDAP / Active Directory Configurações
    LDAP_MOCK: bool = True
    LDAP_SERVER: str = "ldap://ad.empresa.com:389"
    LDAP_BASE_DN: str = "DC=empresa,DC=com"
    LDAP_REQUIRED_GROUP: str = "CN=TI_Admin,OU=Groups,DC=empresa,DC=com"
    LDAP_BIND_USER: Optional[str] = None
    LDAP_BIND_PASSWORD: Optional[str] = None
    LDAP_USER_SEARCH_FILTER: str = "(sAMAccountName={username})"

    # Master Password Protection
    MASTER_PASSWORD_USER: Optional[str] = None

settings = Settings()
