from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.crud import category as crud_category
from app.schemas.auth import TokenData
from app.schemas.category import AttributeCreate, AttributeOut, CategoryCreate, CategoryOut, CategoryUpdate, AttributeOrderUpdate, AttributeUpdate

router = APIRouter()

# Garantimos que todas as rotas deste router exigem autenticação do usuário
@router.post("/", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(
    category: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Cria uma nova Categoria juntamente com seus Atributos (Campos dinâmicos).
    """
    db_category = crud_category.get_category_by_name(db, name=category.name)
    if db_category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Uma categoria com o nome '{category.name}' já existe."
        )
    return crud_category.create_category(db=db, category=category)


@router.get("/", response_model=List[CategoryOut])
def read_categories(
    skip: int = 0,
    limit: int = 10000,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Lista todas as categorias cadastradas.
    """
    return crud_category.get_categories(db, skip=skip, limit=limit)


@router.get("/{category_id}", response_model=CategoryOut)
def read_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Recupera os detalhes de uma categoria específica com seus campos configurados.
    """
    db_category = crud_category.get_category(db, category_id=category_id)
    if not db_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria não encontrada."
        )
    return db_category


@router.put("/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int,
    category_update: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Atualiza os detalhes (nome/descrição) de uma categoria específica.
    """
    db_category = crud_category.update_category(db, category_id=category_id, category_update=category_update)
    if not db_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria não encontrada."
        )
    return db_category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Remove uma categoria. IMPORTANTE: Isto deletará em cascata todos os itens e valores cadastrados nela.
    """
    success = crud_category.delete_category(db, category_id=category_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria não encontrada."
        )
    return None


@router.post("/{category_id}/attributes", response_model=AttributeOut, status_code=status.HTTP_201_CREATED)
def add_attribute_to_category(
    category_id: int,
    attribute: AttributeCreate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Adiciona um novo campo/atributo dinâmico a uma categoria existente.
    """
    db_category = crud_category.get_category(db, category_id=category_id)
    if not db_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria não encontrada."
        )
    
    # Verifica se já existe um atributo com o mesmo nome na categoria
    for attr in db_category.attributes:
        if attr.name.lower() == attribute.name.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"O campo '{attribute.name}' já está cadastrado nesta categoria."
            )
            
    return crud_category.add_attribute(db, category_id=category_id, attribute=attribute)


@router.delete("/{category_id}/attributes/{attribute_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_attribute_from_category(
    category_id: int,
    attribute_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Remove um campo/atributo de uma categoria.
    Os valores cadastrados para este campo serão deletados em cascata em todos os itens.
    """
    success = crud_category.delete_attribute(db, category_id=category_id, attribute_id=attribute_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Atributo não encontrado ou não pertence a esta categoria."
        )
    return None

@router.put("/{category_id}/attributes/order", status_code=status.HTTP_200_OK)
def update_attributes_order(
    category_id: int,
    orders: List[AttributeOrderUpdate],
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Atualiza a ordem de exibição dos atributos de uma categoria.
    """
    db_category = crud_category.get_category(db, category_id=category_id)
    if not db_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria não encontrada."
        )
    
    crud_category.update_attributes_order(db, category_id=category_id, orders=orders)
    return {"message": "Ordem atualizada com sucesso."}

@router.put("/{category_id}/attributes/{attribute_id}", response_model=AttributeOut)
def update_attribute_in_category(
    category_id: int,
    attribute_id: int,
    attribute_in: AttributeUpdate,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Edita propriedades (nome ou obrigatoriedade) de um campo existente.
    """
    if attribute_in.name:
        db_category = crud_category.get_category(db, category_id=category_id)
        if db_category:
            for attr in db_category.attributes:
                if attr.id != attribute_id and attr.name.lower() == attribute_in.name.lower():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Já existe outro campo com o nome '{attribute_in.name}' nesta categoria."
                    )

    updated = crud_category.update_attribute(db, category_id=category_id, attribute_id=attribute_id, obj_in=attribute_in)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Atributo não encontrado ou não pertence a esta categoria."
        )
    return updated

@router.put("/order/update", status_code=status.HTTP_200_OK)
def update_categories_order(
    orders: List[AttributeOrderUpdate],
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Atualiza a ordem de exibição das categorias.
    """
    crud_category.update_categories_order(db, orders=orders)
    return {"message": "Ordem das categorias atualizada com sucesso."}
