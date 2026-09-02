from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.eav import Attribute, Category
from app.schemas.category import AttributeCreate, CategoryCreate, CategoryUpdate, AttributeOrderUpdate, AttributeUpdate
from app.core import files as file_manager

def get_category(db: Session, category_id: int) -> Optional[Category]:
    return db.query(Category).filter(Category.id == category_id).first()

def get_category_by_name(db: Session, name: str) -> Optional[Category]:
    return db.query(Category).filter(Category.name == name).first()

def get_categories(db: Session, skip: int = 0, limit: int = 10000) -> List[Category]:
    return db.query(Category).order_by(Category.display_order.asc(), Category.id.asc()).offset(skip).limit(limit).all()

def create_category(db: Session, category: CategoryCreate) -> Category:
    # Cria o objeto de categoria
    db_category = Category(
        name=category.name,
        description=category.description,
        display_order=category.display_order
    )
    db.add(db_category)
    db.flush()  # Obtém o ID da categoria recém-criada

    # Cria e associa os atributos iniciais
    for i, attr in enumerate(category.attributes):
        db_attr = Attribute(
            category_id=db_category.id,
            name=attr.name,
            type=attr.type,
            is_required=attr.is_required,
            display_order=attr.display_order if attr.display_order is not None else i
        )
        db.add(db_attr)
    
    db.commit()
    db.refresh(db_category)
    return db_category

def update_category(db: Session, category_id: int, category_update: CategoryUpdate) -> Optional[Category]:
    db_category = db.query(Category).filter(Category.id == category_id).first()
    if not db_category:
        return None
    
    if category_update.name is not None:
        db_category.name = category_update.name
    if category_update.description is not None:
        db_category.description = category_update.description
    if category_update.display_order is not None:
        db_category.display_order = category_update.display_order
        
    db.commit()
    db.refresh(db_category)
    return db_category


def delete_category(db: Session, category_id: int) -> bool:
    db_category = db.query(Category).filter(Category.id == category_id).first()
    if db_category:
        file_manager.delete_category_files(category_id)
        db.delete(db_category)
        db.commit()
        return True
    return False

def add_attribute(db: Session, category_id: int, attribute: AttributeCreate) -> Attribute:
    db_attribute = Attribute(
        category_id=category_id,
        name=attribute.name,
        type=attribute.type,
        is_required=attribute.is_required,
        display_order=attribute.display_order
    )
    db.add(db_attribute)
    db.commit()
    db.refresh(db_attribute)
    return db_attribute

def delete_attribute(db: Session, category_id: int, attribute_id: int) -> bool:
    db_attribute = db.query(Attribute).filter(
        Attribute.id == attribute_id,
        Attribute.category_id == category_id
    ).first()
    if db_attribute:
        file_manager.delete_attribute_files(category_id, attribute_id)
        db.delete(db_attribute)
        db.commit()
        return True
    return False

def update_attribute(db: Session, category_id: int, attribute_id: int, obj_in: AttributeUpdate) -> Optional[Attribute]:
    db_attribute = db.query(Attribute).filter(
        Attribute.id == attribute_id,
        Attribute.category_id == category_id
    ).first()
    if not db_attribute:
        return None
    
    update_data = obj_in.model_dump(exclude_unset=True)
    for field in update_data:
        setattr(db_attribute, field, update_data[field])
        
    db.add(db_attribute)
    db.commit()
    db.refresh(db_attribute)
    return db_attribute

def update_attributes_order(db: Session, category_id: int, orders: List[AttributeOrderUpdate]) -> bool:
    for order_update in orders:
        db.query(Attribute).filter(
            Attribute.id == order_update.id,
            Attribute.category_id == category_id
        ).update({"display_order": order_update.display_order})
    db.commit()
    return True

def update_categories_order(db: Session, orders: List[AttributeOrderUpdate]) -> bool:
    from app.schemas.category import CategoryOrderUpdate
    for order_update in orders:
        db.query(Category).filter(Category.id == order_update.id).update({"display_order": order_update.display_order})
    db.commit()
    return True

