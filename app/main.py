from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.auth import router as auth_router
from app.api.categories import router as categories_router
from app.api.entities import router as entities_router
from app.api.files import router as files_router
from app.api.dashboard import router as dashboard_router
from app.api.config import router as config_router
from app.core.config import settings
from app.core.database import Base, engine

import time

# Criação das tabelas do banco de dados na inicialização do app (EAV padrão)
max_retries = 5
for attempt in range(max_retries):
    try:
        Base.metadata.create_all(bind=engine)
        print("Tabelas do banco de dados verificadas/criadas com sucesso.")
        
        # Simple migration to ensure display_order exists on categories
        with engine.connect() as conn:
            from sqlalchemy import text
            try:
                # Check if display_order exists
                conn.execute(text("SELECT display_order FROM categories LIMIT 1"))
            except Exception:
                conn.rollback() # Rollback the aborted transaction from failed select
                # Column doesn't exist, we add it
                print("Adicionando coluna display_order em categories...")
                conn.execute(text("ALTER TABLE categories ADD COLUMN display_order INTEGER DEFAULT 0 NOT NULL"))
                conn.commit()

            try:
                # Simple migration to ensure RICH_TEXT enum exists
                res = conn.execute(text("SELECT 1 FROM pg_enum JOIN pg_type ON pg_enum.enumtypid = pg_type.oid WHERE pg_type.typname = 'attributetype' AND pg_enum.enumlabel = 'RICH_TEXT'"))
                if not res.scalar():
                    print("Adicionando RICH_TEXT ao enum attributetype...")
                    conn.commit()
                    # ALTER TYPE cannot run inside a transaction block, so we use AUTOCOMMIT
                    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as auto_conn:
                        auto_conn.execute(text("ALTER TYPE attributetype ADD VALUE 'RICH_TEXT'"))
            except Exception as e:
                print(f"Aviso ao tentar atualizar o enum attributetype: {e}")
                conn.rollback()

        break
    except Exception as e:
        print(f"Tentativa {attempt + 1}/{max_retries} - Banco de dados indisponível, aguardando... ({e})")
        time.sleep(3)
else:
    print("Aviso crítico: Não foi possível conectar ao banco de dados após várias tentativas. O sistema pode apresentar falhas.")

app = FastAPI(
    title="IT Doc System API",
    description="Sistema autohospedado dinâmico para gerenciamento e documentação de ativos e informações de TI (EAV + LDAP).",
    version="1.0.0",
)

from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware
from app.core.rate_limit import limiter

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Configuração de CORS para permitir acesso do frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Registro dos Routers da API
app.include_router(auth_router, prefix="/api/auth", tags=["Autenticação"])
app.include_router(categories_router, prefix="/api/categories", tags=["Categorias"])
app.include_router(entities_router, prefix="/api/categories/{category_id}/items", tags=["Itens Dinâmicos (Equipamentos)"])
app.include_router(files_router, prefix="/api/files", tags=["Arquivos"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(config_router, prefix="/api/config", tags=["Configuração"])

@app.get("/", include_in_schema=False)
def root_redirect():
    """
    Redireciona a rota raiz para a documentação interativa Swagger.
    """
    return RedirectResponse(url="/docs")


@app.get("/api/status", tags=["Status"])
def api_status():
    """
    Retorna o status atual de funcionamento do sistema e o modo do LDAP.
    """
    return {
        "status": "online",
        "ldap_mode": "mock" if settings.LDAP_MOCK else "active_directory",
        "ldap_required_group": settings.LDAP_REQUIRED_GROUP,
        "database": "connected (tables initialized)"
    }
