import logging
from datetime import datetime, timedelta
from typing import List, Optional
import ldap3
from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.config import settings
from app.schemas.auth import TokenData

logger = logging.getLogger(__name__)

# Configurações de expiração padrão
JWT_SECRET_KEY = settings.JWT_SECRET_KEY
JWT_ALGORITHM = settings.JWT_ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Gera um token JWT para o usuário autenticado.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[TokenData]:
    """
    Decodifica e valida as claims de um token JWT.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: str = payload.get("sub")
        groups: List[str] = payload.get("groups", [])
        if username is None:
            return None
        return TokenData(username=username, groups=groups)
    except JWTError:
        return None


def authenticate_ldap_mock(username: str, password: str) -> Optional[dict]:
    """
    Simulação de autenticação LDAP para desenvolvimento local.
    Qualquer login é aceito se a senha for 'senha123' ou 'admin'.
    """
    logger.info(f"[LDAP MOCK] Tentativa de login para o usuário: {username}")
    if password in ("senha123", "admin", username):
        mock_user = {
            "username": username,
            "name": f"{username.capitalize()} Mock AD User",
            "email": f"{username}@empresa.com",
            "groups": [
                settings.LDAP_REQUIRED_GROUP,
                "CN=Domain Users,CN=Users,DC=empresa,DC=com"
            ]
        }
        logger.info(f"[LDAP MOCK] Login bem-sucedido para {username}. Pertence ao grupo requerido.")
        return mock_user
    logger.warning(f"[LDAP MOCK] Credenciais inválidas para o usuário: {username}")
    return None


def authenticate_ldap(username: str, password: str) -> Optional[dict]:
    """
    Autenticação real contra o Active Directory (Windows Server).
    Realiza busca do usuário pelo sAMAccountName, valida a senha com bind
    e verifica se o usuário pertence ao grupo exigido.
    """
    if settings.LDAP_MOCK:
        return authenticate_ldap_mock(username, password)

    try:
        # 1. Configura o servidor AD
        server = ldap3.Server(settings.LDAP_SERVER, get_info=ldap3.ALL)
        
        # 2. Conecta usando a conta de serviço (Service Account / Bind DN) para pesquisar o DN do usuário
        # Caso não haja bind user configurado, tentamos o bind direto posteriormente.
        if settings.LDAP_BIND_USER and settings.LDAP_BIND_PASSWORD:
            conn = ldap3.Connection(
                server,
                user=settings.LDAP_BIND_USER,
                password=settings.LDAP_BIND_PASSWORD,
                auto_bind=True
            )
        else:
            # Em AD padrão, bind anônimo geralmente é desabilitado. Recomendado usar bind user.
            conn = ldap3.Connection(server, auto_bind=True)

        # 3. Executa a pesquisa para achar o DN do usuário pelo seu sAMAccountName
        search_filter = settings.LDAP_USER_SEARCH_FILTER.format(username=username)
        # Campos desejados do AD: distinguishedName, cn, mail, memberOf
        conn.search(
            search_base=settings.LDAP_BASE_DN,
            search_filter=search_filter,
            attributes=["cn", "mail", "memberOf", "distinguishedName"]
        )

        if not conn.entries:
            logger.warning(f"Usuário LDAP não encontrado: {username}")
            return None

        user_entry = conn.entries[0]
        user_dn = user_entry.entry_dn
        
        # CN/Nome amigável e e-mail
        cn_value = user_entry.cn.value if hasattr(user_entry, "cn") and user_entry.cn else username
        mail_value = user_entry.mail.value if hasattr(user_entry, "mail") and user_entry.mail else None
        
        # Grupos aos quais o usuário pertence
        # No AD, groups retornados no atributo 'memberOf' são DNs completos
        groups = []
        if hasattr(user_entry, "memberOf") and user_entry.memberOf:
            groups = list(user_entry.memberOf.values)

        # 4. Tenta fazer BIND (autenticar senha) usando o DN do próprio usuário e a senha fornecida
        user_conn = ldap3.Connection(server, user=user_dn, password=password)
        if not user_conn.bind():
            logger.warning(f"Senha incorreta para o usuário LDAP: {username}")
            return None

        # 5. Verifica se o usuário pertence ao grupo requerido
        required_group_dn = settings.LDAP_REQUIRED_GROUP.lower()
        # Verifica se o grupo requerido está na lista (ou correspondência direta de CN)
        belongs_to_group = False
        for grp in groups:
            grp_lower = grp.lower()
            if grp_lower == required_group_dn or f"cn={required_group_dn}," in grp_lower:
                belongs_to_group = True
                break
        
        # Se não houver correspondência, tentamos uma comparação simples por nome do grupo (CN)
        # Caso o LDAP_REQUIRED_GROUP seja apenas o nome do CN e não o DN completo
        if not belongs_to_group:
            # Ex: se config for apenas "TI_Admin" ao invés de "CN=TI_Admin,..."
            for grp in groups:
                # Extrai o CN do grupo ex: CN=TI_Admin,OU=Groups... -> TI_Admin
                parts = grp.split(",")
                for part in parts:
                    if part.lower().startswith("cn="):
                        cn_group = part.split("=")[1].strip()
                        if cn_group.lower() == required_group_dn:
                            belongs_to_group = True
                            break

        if not belongs_to_group:
            logger.warning(f"Usuário {username} autenticado com sucesso, mas não pertence ao grupo de acesso: {settings.LDAP_REQUIRED_GROUP}")
            return None

        logger.info(f"Usuário {username} autenticado e autorizado via LDAP Active Directory.")
        return {
            "username": username,
            "name": cn_value,
            "email": mail_value,
            "groups": groups
        }

    except Exception as e:
        logger.error(f"Erro inesperado durante a autenticação LDAP: {str(e)}")
        # Se ocorrer erro operacional e o mock estiver habilitado como fallback alternativo, use:
        if settings.LDAP_MOCK:
            logger.info("Erro de LDAP real detectado. Executando fallback para LDAP MOCK.")
            return authenticate_ldap_mock(username, password)
        return None
