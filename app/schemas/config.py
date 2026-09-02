from pydantic import BaseModel
from typing import Optional

class MasterPasswordSetup(BaseModel):
    master_password: str

class MasterPasswordChange(BaseModel):
    old_password: str
    new_password: str

class MasterPasswordStatus(BaseModel):
    is_setup: bool
    can_manage: bool
