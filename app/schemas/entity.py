from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, create_model

from app.models.eav import Attribute, AttributeType

class EntityOut(BaseModel):
    id: int
    category_id: int
    created_at: datetime
    updated_at: datetime
    properties: Dict[str, Any]

    class Config:
        from_attributes = True


def generate_pydantic_validator(
    category_attributes: List[Attribute], is_update: bool = False
) -> type[BaseModel]:
    """
    Cria dinamicamente uma classe Pydantic baseada nos atributos da categoria
    cadastrados no banco. Esta classe dinâmica valida os tipos de dados informados.
    """
    fields = {}
    for attr in category_attributes:
        # Mapeia tipo do BD para o correspondente tipo do Python
        if attr.type == AttributeType.STRING:
            py_type = str
        elif attr.type == AttributeType.INTEGER:
            py_type = int
        elif attr.type == AttributeType.DATE:
            # Pydantic converterá strings "YYYY-MM-DD" em objetos date do python automaticamente
            py_type = date
        elif attr.type == AttributeType.BOOLEAN:
            py_type = bool
        elif attr.type == AttributeType.PASSWORD:
            py_type = str
        elif attr.type == AttributeType.FILE:
            py_type = str
        elif attr.type == AttributeType.RICH_TEXT:
            py_type = str
        else:
            py_type = str

        # Se for uma atualização ou o campo não for obrigatório, define Optional
        if is_update or not attr.is_required:
            py_type = Optional[py_type]
            fields[attr.name] = (py_type, None)
        else:
            # Significa que o campo é obrigatório (...)
            fields[attr.name] = (py_type, ...)

    # Criação do modelo Pydantic em runtime
    return create_model("DynamicItemValidator", **fields)
