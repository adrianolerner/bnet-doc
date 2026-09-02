import os
import base64
import bcrypt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

def verify_master_password_hash(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_master_password_hash(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def generate_salt() -> str:
    return os.urandom(16).hex()

def derive_key(master_password: str, salt: bytes) -> bytes:
    """
    Derives a 32-byte url-safe base64 key from the master password and salt using PBKDF2.
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=390000,
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(master_password.encode('utf-8')))
    return key

def encrypt_password(plain_password: str, master_password: str, salt: str) -> str:
    """
    Encrypts a plain password using a key derived from the master password and salt (hex).
    """
    key = derive_key(master_password, bytes.fromhex(salt))
    f = Fernet(key)
    return f.encrypt(plain_password.encode('utf-8')).decode('utf-8')

def decrypt_password(encrypted_password: str, master_password: str, salt: str) -> str:
    """
    Decrypts an encrypted password using a key derived from the master password and salt (hex).
    """
    key = derive_key(master_password, bytes.fromhex(salt))
    f = Fernet(key)
    return f.decrypt(encrypted_password.encode('utf-8')).decode('utf-8')
