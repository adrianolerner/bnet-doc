from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.api.deps import get_db, get_current_user
from app.models.eav import Category, Entity
from app.schemas.auth import TokenData

router = APIRouter()

@router.get("/stats", response_model=Dict[str, Any])
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Retorna estatísticas gerais para o dashboard:
    - Quantidade de itens por categoria
    - Últimos itens modificados no sistema
    """
    
    # Busca todas as categorias
    categories = db.query(Category).all()
    
    category_counts = []
    for cat in categories:
        count = db.query(Entity).filter(Entity.category_id == cat.id).count()
        category_counts.append({
            "id": cat.id,
            "name": cat.name,
            "count": count
        })
        
    # Busca os ultimos itens atualizados
    recent_entities = db.query(Entity).order_by(desc(Entity.updated_at)).limit(5).all()
    recent_items = []
    
    for entity in recent_entities:
        recent_items.append({
            "id": entity.id,
            "category_name": entity.category.name if entity.category else "Desconhecida",
            "updated_at": entity.updated_at.isoformat()
        })
        
    return {
        "category_counts": category_counts,
        "recent_items": recent_items
    }

@router.get("/logs", response_model=List[Dict[str, Any]])
def get_modification_logs(
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Retorna os 100 últimos registros de modificações feitas no sistema.
    """
    from app.models.eav import ModificationLog
    logs = db.query(ModificationLog).order_by(desc(ModificationLog.created_at)).limit(100).all()
    
    return [
        {
            "id": log.id,
            "entity_id": log.entity_id,
            "category_name": log.category_name,
            "action": log.action,
            "username": log.username,
            "created_at": log.created_at.isoformat()
        }
        for log in logs
    ]
