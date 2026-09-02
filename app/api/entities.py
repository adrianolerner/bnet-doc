from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.crud import category as crud_category
from app.crud import entity as crud_entity
from app.schemas.auth import TokenData
from app.schemas.entity import EntityOut, generate_pydantic_validator
from app.models.eav import SystemConfig, AttributeType, ModificationLog
from app.core.crypto import verify_master_password_hash, encrypt_password, decrypt_password
import bleach
from bleach.css_sanitizer import CSSSanitizer

css_sanitizer = CSSSanitizer(allowed_css_properties=['color', 'background-color', 'text-align', 'font-size', 'font-family'])

router = APIRouter()

@router.post("/", response_model=EntityOut, status_code=status.HTTP_201_CREATED)
def create_item(
    category_id: int,
    payload: Dict[str, Any],
    x_master_password: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Cria um novo item (Entity/Values) sob uma categoria.
    O payload é validado dinamicamente com base nos atributos definidos para a categoria.
    """
    db_category = crud_category.get_category(db, category_id=category_id)
    if not db_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria não encontrada."
        )

    # 1. Gera o validador dinâmico do Pydantic para esta categoria
    Validator = generate_pydantic_validator(db_category.attributes, is_update=False)

    # 2. Executa a validação do payload
    try:
        validated_data = Validator(**payload).model_dump()
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors()
        )

    # 2.2 Sanitize RichText HTML to prevent XSS
    rich_text_attrs = [a for a in db_category.attributes if a.type == AttributeType.RICH_TEXT]
    for attr in rich_text_attrs:
        if attr.name in validated_data and validated_data[attr.name]:
            validated_data[attr.name] = bleach.clean(
                validated_data[attr.name],
                tags=['p', 'br', 'strong', 'em', 'u', 's', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'pre', 'ul', 'ol', 'li', 'span', 'a', 'img', 'div'],
                attributes={'*': ['class', 'style'], 'a': ['href', 'target', 'rel'], 'img': ['src', 'alt', 'width', 'height']},
                css_sanitizer=css_sanitizer,
                protocols=['http', 'https', 'data'] # allow data URIs for images if any remain, but mostly http/https
            )

    # 2.5 Encrypt passwords if they exist
    password_attrs = [a for a in db_category.attributes if a.type == AttributeType.PASSWORD]
    has_passwords_to_encrypt = any(
        attr.name in validated_data and validated_data[attr.name] is not None
        for attr in password_attrs
    )
    
    if has_passwords_to_encrypt:
        if not x_master_password:
            raise HTTPException(status_code=400, detail="Master password required to encrypt data.")
        
        config_hash = db.query(SystemConfig).filter(SystemConfig.key == "master_password_hash").first()
        config_salt = db.query(SystemConfig).filter(SystemConfig.key == "master_password_salt").first()
        
        if not config_hash or not config_salt:
            raise HTTPException(status_code=400, detail="Master password not configured yet.")
            
        if not verify_master_password_hash(x_master_password, config_hash.value):
            raise HTTPException(status_code=400, detail="Invalid master password.")
            
        for attr in password_attrs:
            if attr.name in validated_data and validated_data[attr.name]:
                validated_data[attr.name] = encrypt_password(
                    validated_data[attr.name], x_master_password, config_salt.value
                )

    # 3. Cria a entidade no banco mapeando os tipos
    db_entity = crud_entity.create_entity(
        db=db,
        category_id=category_id,
        properties=validated_data,
        attributes=db_category.attributes
    )

    # 4. Grava o log de modificação
    db_log = ModificationLog(
        entity_id=db_entity.id,
        category_name=db_category.name,
        action="CREATE",
        username=current_user.username
    )
    db.add(db_log)
    db.commit()

    # 5. Formata o output
    return EntityOut(
        id=db_entity.id,
        category_id=db_entity.category_id,
        created_at=db_entity.created_at,
        updated_at=db_entity.updated_at,
        properties=crud_entity.flat_entity_properties(db_entity)
    )


@router.get("/", response_model=List[EntityOut])
def read_items(
    category_id: int,
    skip: int = 0,
    limit: int = 10000,
    x_master_password: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Lista todos os itens cadastrados em uma categoria específica.
    Se X-Master-Password for fornecido e válido, descriptografa os campos de senha.
    """
    db_category = crud_category.get_category(db, category_id=category_id)
    if not db_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria não encontrada."
        )

    db_entities = crud_entity.get_entities_by_category(db, category_id=category_id, skip=skip, limit=limit)
    
    # Prepara configs de senha, se solicitada a descriptografia
    config_hash = None
    config_salt = None
    if x_master_password:
        config_hash = db.query(SystemConfig).filter(SystemConfig.key == "master_password_hash").first()
        config_salt = db.query(SystemConfig).filter(SystemConfig.key == "master_password_salt").first()
        if not config_hash or not config_salt or not verify_master_password_hash(x_master_password, config_hash.value):
            raise HTTPException(status_code=400, detail="Invalid master password.")

    results = []
    for ent in db_entities:
        props = crud_entity.flat_entity_properties(ent)
        if x_master_password and config_salt:
            for val in ent.values:
                attr = val.attribute
                if attr and attr.type == AttributeType.PASSWORD and val.value_string:
                    try:
                        props[attr.name] = decrypt_password(val.value_string, x_master_password, config_salt.value)
                    except Exception:
                        props[attr.name] = "ERROR_DECRYPTING"
        results.append(EntityOut(
            id=ent.id,
            category_id=ent.category_id,
            created_at=ent.created_at,
            updated_at=ent.updated_at,
            properties=props
        ))
        
    return results


@router.get("/{item_id}", response_model=EntityOut)
def read_item(
    category_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Recupera os detalhes de um item específico pertencente a uma categoria.
    """
    db_entity = crud_entity.get_entity(db, category_id=category_id, entity_id=item_id)
    if not db_entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item não encontrado nesta categoria."
        )

    return EntityOut(
        id=db_entity.id,
        category_id=db_entity.category_id,
        created_at=db_entity.created_at,
        updated_at=db_entity.updated_at,
        properties=crud_entity.flat_entity_properties(db_entity)
    )


@router.put("/{item_id}", response_model=EntityOut)
def update_item(
    category_id: int,
    item_id: int,
    payload: Dict[str, Any],
    x_master_password: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Atualiza parcialmente/totalmente os atributos de um item existente.
    A validação garante compatibilidade com os tipos declarados na categoria.
    """
    db_category = crud_category.get_category(db, category_id=category_id)
    if not db_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Categoria não encontrada."
        )

    # 1. Gera o validador com campos opcionais para atualizações parciais
    Validator = generate_pydantic_validator(db_category.attributes, is_update=True)

    # 2. Executa a validação
    try:
        # Filtramos para remover campos não definidos no payload da requisição para manter o padrão PUT parcial
        # mas mantemos os None explícitos que o usuário queira atualizar para nulo.
        validated_data = Validator(**payload).model_dump(exclude_unset=True)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors()
        )

    # 2.2 Sanitize RichText HTML to prevent XSS
    rich_text_attrs = [a for a in db_category.attributes if a.type == AttributeType.RICH_TEXT]
    for attr in rich_text_attrs:
        if attr.name in validated_data and validated_data[attr.name]:
            validated_data[attr.name] = bleach.clean(
                validated_data[attr.name],
                tags=['p', 'br', 'strong', 'em', 'u', 's', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'pre', 'ul', 'ol', 'li', 'span', 'a', 'img', 'div'],
                attributes={'*': ['class', 'style'], 'a': ['href', 'target', 'rel'], 'img': ['src', 'alt', 'width', 'height']},
                css_sanitizer=css_sanitizer,
                protocols=['http', 'https', 'data']
            )

    # 2.5 Encrypt passwords if they exist and are updated
    password_attrs = [a for a in db_category.attributes if a.type == AttributeType.PASSWORD]
    has_passwords_to_encrypt = any(
        attr.name in validated_data and validated_data[attr.name] is not None and validated_data[attr.name] != "********" and validated_data[attr.name] != "-"
        for attr in password_attrs
    )
    
    if has_passwords_to_encrypt:
        if not x_master_password:
            raise HTTPException(status_code=400, detail="Master password required to encrypt new passwords.")
        
        config_hash = db.query(SystemConfig).filter(SystemConfig.key == "master_password_hash").first()
        config_salt = db.query(SystemConfig).filter(SystemConfig.key == "master_password_salt").first()
        
        if not config_hash or not config_salt:
            raise HTTPException(status_code=400, detail="Master password not configured yet.")
            
        if not verify_master_password_hash(x_master_password, config_hash.value):
            raise HTTPException(status_code=400, detail="Invalid master password.")
            
        for attr in password_attrs:
            if attr.name in validated_data and validated_data[attr.name] and validated_data[attr.name] not in ("********", "-"):
                validated_data[attr.name] = encrypt_password(
                    validated_data[attr.name], x_master_password, config_salt.value
                )
            else:
                # Se o payload enviar "********" ou "-", significa que não mudou e podemos remover do dicionário de update
                validated_data.pop(attr.name, None)

    # 3. Atualiza os dados no banco
    db_entity = crud_entity.update_entity(
        db=db,
        category_id=category_id,
        entity_id=item_id,
        properties=validated_data,
        attributes=db_category.attributes
    )

    if not db_entity:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item não encontrado nesta categoria."
        )

    db_log = ModificationLog(
        entity_id=db_entity.id,
        category_name=db_category.name,
        action="UPDATE",
        username=current_user.username
    )
    db.add(db_log)
    db.commit()

    return EntityOut(
        id=db_entity.id,
        category_id=db_entity.category_id,
        created_at=db_entity.created_at,
        updated_at=db_entity.updated_at,
        properties=crud_entity.flat_entity_properties(db_entity)
    )


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    category_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Remove um item e todos os seus valores associados da categoria.
    """
    db_category = crud_category.get_category(db, category_id=category_id)
    cat_name = db_category.name if db_category else "Desconhecida"

    success = crud_entity.delete_entity(db, category_id=category_id, entity_id=item_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item não encontrado nesta categoria."
        )
        
    db_log = ModificationLog(
        entity_id=item_id,
        category_name=cat_name,
        action="DELETE",
        username=current_user.username
    )
    db.add(db_log)
    db.commit()
        
    return None

class RevealPasswordPayload(BaseModel):
    master_password: str

@router.post("/{item_id}/reveal", response_model=Dict[str, str])
def reveal_item_password(
    category_id: int,
    item_id: int,
    payload: RevealPasswordPayload,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    """
    Descriptografa todos os campos de senha de um item fornecendo a senha mestra.
    Retorna um dicionário { "nome_do_campo": "senha_descriptografada" }
    """
    db_entity = crud_entity.get_entity(db, category_id=category_id, entity_id=item_id)
    if not db_entity:
        raise HTTPException(status_code=404, detail="Item não encontrado.")
        
    config_hash = db.query(SystemConfig).filter(SystemConfig.key == "master_password_hash").first()
    config_salt = db.query(SystemConfig).filter(SystemConfig.key == "master_password_salt").first()
    
    if not config_hash or not config_salt:
        raise HTTPException(status_code=400, detail="Master password not configured yet.")
        
    if not verify_master_password_hash(payload.master_password, config_hash.value):
        raise HTTPException(status_code=400, detail="Invalid master password.")
        
    decrypted_passwords = {}
    
    for value_obj in db_entity.values:
        attr = value_obj.attribute
        if attr and attr.type == AttributeType.PASSWORD:
            encrypted_val = value_obj.value_string
            if encrypted_val:
                try:
                    decrypted = decrypt_password(encrypted_val, payload.master_password, config_salt.value)
                    decrypted_passwords[attr.name] = decrypted
                except Exception:
                    decrypted_passwords[attr.name] = "ERROR_DECRYPTING"
            else:
                decrypted_passwords[attr.name] = ""
                
    return decrypted_passwords
