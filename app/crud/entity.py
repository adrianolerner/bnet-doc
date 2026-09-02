from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session, joinedload

from app.models.eav import Attribute, AttributeType, Entity, Value
from app.schemas.entity import generate_pydantic_validator
from app.core import files as file_manager

def flat_entity_properties(entity: Entity) -> Dict[str, Any]:
    """
    Transforma as linhas da tabela 'values' associadas a um item (Entity)
    em um dicionário chave-valor plano (ex: {"Modelo": "Dell", "IP": "10.0.0.1"}).
    """
    properties = {}
    for val in entity.values:
        attr = val.attribute
        # Se por algum motivo o atributo foi deletado, ignora
        if not attr:
            continue
        
        # Seleciona o campo correto com base no tipo físico
        if attr.type in (AttributeType.STRING, AttributeType.FILE, AttributeType.RICH_TEXT):
            properties[attr.name] = val.value_string
        elif attr.type == AttributeType.PASSWORD:
            properties[attr.name] = "********"
        elif attr.type == AttributeType.INTEGER:
            properties[attr.name] = val.value_integer
        elif attr.type == AttributeType.DATE:
            # Pydantic cuidará da conversão de data para string no output
            properties[attr.name] = val.value_date
        elif attr.type == AttributeType.BOOLEAN:
            properties[attr.name] = val.value_boolean
            
    return properties


def get_entity(db: Session, category_id: int, entity_id: int) -> Optional[Entity]:
    """
    Recupera uma entidade carregando ansiosamente (eager loading) 
    seus valores e os metadados dos atributos.
    """
    return db.query(Entity).filter(
        Entity.id == entity_id,
        Entity.category_id == category_id
    ).options(
        joinedload(Entity.values).joinedload(Value.attribute)
    ).first()


def get_entities_by_category(db: Session, category_id: int, skip: int = 0, limit: int = 10000) -> List[Entity]:
    """
    Lista todas as entidades de uma categoria carregando seus relacionamentos de valores.
    """
    return db.query(Entity).filter(
        Entity.category_id == category_id
    ).options(
        joinedload(Entity.values).joinedload(Value.attribute)
    ).offset(skip).limit(limit).all()


def create_entity(db: Session, category_id: int, properties: Dict[str, Any], attributes: List[Attribute]) -> Entity:
    """
    Cria uma nova entidade dinamicamente a partir dos campos validados.
    """
    # 1. Instancia a Entidade
    db_entity = Entity(category_id=category_id)
    db.add(db_entity)
    db.flush()  # Gera o ID do item

    # 2. Para cada atributo da categoria, mapeia o valor recebido e insere na tabela 'values'
    for attr in attributes:
        val_to_save = properties.get(attr.name)
        
        # Ignora campos opcionais não informados (serão implicitamente nulos)
        if val_to_save is None:
            continue

        db_value = Value(
            entity_id=db_entity.id,
            attribute_id=attr.id
        )

        # Preenche a coluna física de acordo com o tipo lógico definido no atributo
        if attr.type in (AttributeType.STRING, AttributeType.PASSWORD, AttributeType.RICH_TEXT):
            db_value.value_string = str(val_to_save)
        elif attr.type == AttributeType.FILE:
            perm_path = file_manager.move_temp_file_to_permanent(str(val_to_save), category_id, db_entity.id, attr.id)
            db_value.value_string = perm_path
        elif attr.type == AttributeType.INTEGER:
            db_value.value_integer = int(val_to_save)
        elif attr.type == AttributeType.DATE:
            db_value.value_date = val_to_save  # O tipo date mapeado via dynamic Pydantic já é um objeto 'date'
        elif attr.type == AttributeType.BOOLEAN:
            db_value.value_boolean = bool(val_to_save)

        db.add(db_value)

    db.commit()
    db.refresh(db_entity)
    return db_entity


def update_entity(
    db: Session, 
    category_id: int, 
    entity_id: int, 
    properties: Dict[str, Any], 
    attributes: List[Attribute]
) -> Optional[Entity]:
    """
    Atualiza uma entidade existente. Atualiza valores modificados ou insere novos registros
    caso campos opcionais vazios tenham sido preenchidos.
    """
    db_entity = get_entity(db, category_id, entity_id)
    if not db_entity:
        return None

    # Mapeia os valores existentes por id do atributo para acesso rápido
    existing_values = {v.attribute_id: v for v in db_entity.values}

    for attr in attributes:
        if attr.name not in properties:
            # Se o campo não foi enviado no payload de atualização, mantém o atual
            continue

        val_to_save = properties[attr.name]
        db_val = existing_values.get(attr.id)

        # Se o valor enviado for None/nulo, deleta a linha de valor caso ela exista
        if val_to_save is None:
            if db_val:
                if attr.type == AttributeType.FILE and db_val.value_string:
                    file_manager.delete_file(db_val.value_string)
                db.delete(db_val)
            continue

        # Se não existe registro de valor anterior para esse campo, cria um novo
        if not db_val:
            db_val = Value(entity_id=db_entity.id, attribute_id=attr.id)
            db.add(db_val)

        # Se for atributo de arquivo, captura o caminho anterior antes de resetar a coluna
        old_file_path = None
        if attr.type == AttributeType.FILE:
            old_file_path = db_val.value_string

        # Reseta os outros campos de valor para nulo para garantir consistência
        db_val.value_string = None
        db_val.value_integer = None
        db_val.value_date = None
        db_val.value_boolean = None

        # Grava na coluna física correta de acordo com a tipagem
        if attr.type in (AttributeType.STRING, AttributeType.PASSWORD, AttributeType.RICH_TEXT):
            db_val.value_string = str(val_to_save)
        elif attr.type == AttributeType.FILE:
            if old_file_path and old_file_path != val_to_save:
                file_manager.delete_file(old_file_path)
            perm_path = file_manager.move_temp_file_to_permanent(str(val_to_save), category_id, entity_id, attr.id)
            db_val.value_string = perm_path
        elif attr.type == AttributeType.INTEGER:
            db_val.value_integer = int(val_to_save)
        elif attr.type == AttributeType.DATE:
            db_val.value_date = val_to_save
        elif attr.type == AttributeType.BOOLEAN:
            db_val.value_boolean = bool(val_to_save)

    db.commit()
    db.refresh(db_entity)
    return db_entity


def delete_entity(db: Session, category_id: int, entity_id: int) -> bool:
    """
    Deleta uma entidade. A deleção em cascata configurada no ORM se encarrega dos Values.
    """
    db_entity = db.query(Entity).filter(
        Entity.id == entity_id,
        Entity.category_id == category_id
    ).first()

    if db_entity:
        file_manager.delete_entity_files(category_id, entity_id)
        db.delete(db_entity)
        db.commit()
        return True
    return False
