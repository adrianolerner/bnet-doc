from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.models.eav import AttributeType

# --- Schemas de Atributos/Campos Customizados ---

class AttributeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Nome do atributo")
    type: AttributeType = Field(..., description="Tipo de dados do campo")
    is_required: bool = Field(False, description="Define se o preenchimento é obrigatório")
    display_order: int = Field(0, description="Ordem de exibição do atributo")

class AttributeCreate(AttributeBase):
    pass

class AttributeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Nome do atributo")
    is_required: Optional[bool] = Field(None, description="Define se o preenchimento é obrigatório")

class AttributeOut(AttributeBase):
    id: int
    category_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AttributeOrderUpdate(BaseModel):
    id: int
    display_order: int


# --- Schemas de Categorias ---

class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Nome da categoria")
    description: Optional[str] = Field(None, description="Descrição detalhada do tipo de equipamento")
    display_order: int = Field(0, description="Ordem de exibição da categoria")

class CategoryOrderUpdate(BaseModel):
    id: int
    display_order: int

class CategoryCreate(CategoryBase):
    attributes: List[AttributeCreate] = Field(
        default=[], description="Lista de campos dinâmicos associados a esta categoria"
    )

class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255, description="Nome da categoria")
    description: Optional[str] = Field(None, description="Descrição detalhada do tipo de equipamento")
    display_order: Optional[int] = Field(None, description="Ordem de exibição da categoria")

class CategoryOut(CategoryBase):
    id: int
    created_at: datetime
    updated_at: datetime
    attributes: List[AttributeOut]

    class Config:
        from_attributes = True
