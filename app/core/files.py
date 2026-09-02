import os
import shutil
import uuid
from fastapi import UploadFile

UPLOAD_DIR = "uploads"
TEMP_DIR = os.path.join(UPLOAD_DIR, "temp")

def init_upload_dirs():
    os.makedirs(TEMP_DIR, exist_ok=True)

def save_temp_file(file: UploadFile) -> str:
    init_upload_dirs()
    # Generates a safe name/dir
    file_id = str(uuid.uuid4())
    temp_file_dir = os.path.join(TEMP_DIR, file_id)
    os.makedirs(temp_file_dir, exist_ok=True)
    
    # Clean filename to avoid issues
    filename = os.path.basename(file.filename)
    dest_path = os.path.join(temp_file_dir, filename)
    
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Return path relative to the app root using forward slashes (web friendly)
    return f"uploads/temp/{file_id}/{filename}"

def move_temp_file_to_permanent(temp_path: str, category_id: int, entity_id: int, attribute_id: int) -> str:
    if not temp_path or not temp_path.startswith("uploads/temp/"):
        return temp_path
        
    # Convert path to system path format
    parts = temp_path.replace("\\", "/").split("/")
    if len(parts) < 4:
        return temp_path
        
    file_id = parts[2]
    filename = parts[3]
    
    system_temp_path = os.path.join(TEMP_DIR, file_id, filename)
    if not os.path.exists(system_temp_path):
        return temp_path
        
    # Target directory: uploads/category_{category_id}/entity_{entity_id}/attr_{attribute_id}/
    dest_dir = os.path.join(UPLOAD_DIR, f"category_{category_id}", f"entity_{entity_id}", f"attr_{attribute_id}")
    os.makedirs(dest_dir, exist_ok=True)
    
    dest_path = os.path.join(dest_dir, filename)
    
    # Move the file
    shutil.move(system_temp_path, dest_path)
    
    # Remove empty temp directory
    try:
        os.rmdir(os.path.join(TEMP_DIR, file_id))
    except Exception:
        pass
        
    return f"uploads/category_{category_id}/entity_{entity_id}/attr_{attribute_id}/{filename}"

def delete_file(file_path: str):
    if not file_path:
        return
        
    # Normalize slashes
    normalized_path = file_path.replace("/", os.sep).replace("\\", os.sep)
    system_path = os.path.abspath(normalized_path)
    
    # Security: Ensure we only delete inside the UPLOAD_DIR
    upload_abs_path = os.path.abspath(UPLOAD_DIR)
    if not system_path.startswith(upload_abs_path):
        return
        
    if os.path.exists(system_path) and os.path.isfile(system_path):
        os.remove(system_path)
        
    # Clean up empty parent directories
    parent_dir = os.path.dirname(system_path)
    while parent_dir != upload_abs_path:
        try:
            if not os.listdir(parent_dir):
                os.rmdir(parent_dir)
                parent_dir = os.path.dirname(parent_dir)
            else:
                break
        except Exception:
            break

def delete_category_files(category_id: int):
    cat_dir = os.path.join(UPLOAD_DIR, f"category_{category_id}")
    if os.path.exists(cat_dir) and os.path.isdir(cat_dir):
        shutil.rmtree(cat_dir)

def delete_entity_files(category_id: int, entity_id: int):
    entity_dir = os.path.join(UPLOAD_DIR, f"category_{category_id}", f"entity_{entity_id}")
    if os.path.exists(entity_dir) and os.path.isdir(entity_dir):
        shutil.rmtree(entity_dir)
        # Clean category dir if empty
        cat_dir = os.path.dirname(entity_dir)
        try:
            if not os.listdir(cat_dir):
                os.rmdir(cat_dir)
        except Exception:
            pass

def delete_attribute_files(category_id: int, attribute_id: int):
    # Find all attr_{attribute_id} directories in uploads/category_{category_id}/entity_*/attr_{attribute_id}
    cat_dir = os.path.join(UPLOAD_DIR, f"category_{category_id}")
    if not os.path.exists(cat_dir) or not os.path.isdir(cat_dir):
        return
        
    for entity_name in os.listdir(cat_dir):
        entity_dir = os.path.join(cat_dir, entity_name)
        if os.path.isdir(entity_dir):
            attr_dir = os.path.join(entity_dir, f"attr_{attribute_id}")
            if os.path.exists(attr_dir) and os.path.isdir(attr_dir):
                shutil.rmtree(attr_dir)
                
            # Clean entity dir if empty
            try:
                if not os.listdir(entity_dir):
                    os.rmdir(entity_dir)
            except Exception:
                pass
