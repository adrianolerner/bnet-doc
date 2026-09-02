import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.eav import SystemConfig, Entity, Category, AttributeType
from app.schemas.config import MasterPasswordSetup, MasterPasswordChange, MasterPasswordStatus
from app.schemas.auth import TokenData
from app.core.crypto import get_master_password_hash, verify_master_password_hash, generate_salt, encrypt_password, decrypt_password
from app.api.deps import get_current_user
from app.core.config import settings

router = APIRouter()

@router.get("/master-password/status", response_model=MasterPasswordStatus)
def get_master_password_status(db: Session = Depends(get_db), current_user: TokenData = Depends(get_current_user)):
    config_hash = db.query(SystemConfig).filter(SystemConfig.key == "master_password_hash").first()
    can_manage = True
    if settings.MASTER_PASSWORD_USER:
        can_manage = current_user.username == settings.MASTER_PASSWORD_USER
    return {"is_setup": config_hash is not None, "can_manage": can_manage}

@router.post("/master-password", response_model=dict)
def setup_master_password(
    data: MasterPasswordSetup,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    if settings.MASTER_PASSWORD_USER and current_user.username != settings.MASTER_PASSWORD_USER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to configure the master password.")
        
    config_hash = db.query(SystemConfig).filter(SystemConfig.key == "master_password_hash").first()
    if config_hash:
        raise HTTPException(status_code=400, detail="Master password already configured.")
    
    hashed = get_master_password_hash(data.master_password)
    salt = generate_salt()
    
    db.add(SystemConfig(key="master_password_hash", value=hashed))
    db.add(SystemConfig(key="master_password_salt", value=salt))
    db.commit()
    
    return {"message": "Master password successfully configured."}

@router.post("/master-password/change", response_model=dict)
def change_master_password(
    data: MasterPasswordChange,
    db: Session = Depends(get_db),
    current_user: TokenData = Depends(get_current_user)
):
    if settings.MASTER_PASSWORD_USER and current_user.username != settings.MASTER_PASSWORD_USER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to change the master password.")
        
    config_hash = db.query(SystemConfig).filter(SystemConfig.key == "master_password_hash").first()
    config_salt = db.query(SystemConfig).filter(SystemConfig.key == "master_password_salt").first()
    
    if not config_hash or not config_salt:
        raise HTTPException(status_code=400, detail="Master password not configured yet.")
        
    if not verify_master_password_hash(data.old_password, config_hash.value):
        raise HTTPException(status_code=400, detail="Invalid old master password.")
        
    old_salt = config_salt.value
    new_hashed = get_master_password_hash(data.new_password)
    new_salt = generate_salt()
    
    # 1. Re-encrypt all stored passwords
    categories = db.query(Category).all()
    for cat in categories:
        password_attrs = [a for a in cat.attributes if a.type == AttributeType.PASSWORD]
        if not password_attrs:
            continue
            
        password_attr_names = [a.name for a in password_attrs]
        for entity in cat.entities:
            needs_update = False
            for value_obj in entity.values:
                attr = value_obj.attribute
                val = getattr(value_obj, f"value_{attr.type.value.lower()}", None)
                
                if attr.name in password_attr_names and val:
                    try:
                        decrypted = decrypt_password(val, data.old_password, old_salt)
                        val = encrypt_password(decrypted, data.new_password, new_salt)
                        value_obj.value_string = val
                        needs_update = True
                    except Exception as e:
                        print(f"Failed to migrate password for entity {entity.id}, attribute {attr.name}: {e}")
                        
            if needs_update:
                db.add(entity)

    # 2. Update SystemConfig
    config_hash.value = new_hashed
    config_salt.value = new_salt
    db.add(config_hash)
    db.add(config_salt)
    
    db.commit()
    return {"message": "Master password successfully changed and data migrated."}
