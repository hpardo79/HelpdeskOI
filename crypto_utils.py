
from cryptography.fernet import Fernet
import os

# --- GESTIÓN DE LA CLAVE DE ENCRIPTACIÓN ---
# En un entorno de producción, esta clave DEBE gestionarse de forma segura,
# por ejemplo, mediante variables de entorno o un servicio de gestión de secretos.
# NO DEBE estar escrita directamente en el código.

# Para generar una nueva clave, puedes usar este código:
# from cryptography.fernet import Fernet
# key = Fernet.generate_key()
# print(key.decode()) # Y guardar esta clave de forma segura.

# Clave hardcodeada para el prototipo (REEMPLAZAR EN PRODUCCIÓN)
ENCRYPTION_KEY = os.environ.get("HELPDESKOI_KEY", "Z1B5Cex_1eCo-sIe_i226zaR33Y_1j4dJ_d-Z_4j_kY=")

if not ENCRYPTION_KEY:
    raise ValueError("La clave de encriptación no está configurada. Defina la variable de entorno HELPDESKOI_KEY.")

cipher_suite = Fernet(ENCRYPTION_KEY.encode())

def encrypt_text(plain_text: str) -> str:
    """Encripta un texto usando la clave del sistema."""
    if not plain_text:
        return ""
    encrypted_bytes = cipher_suite.encrypt(plain_text.encode('utf-8'))
    return encrypted_bytes.decode('utf-8')

def decrypt_text(encrypted_text: str) -> str:
    """Desencripta un texto usando la clave del sistema."""
    if not encrypted_text:
        return ""
    decrypted_bytes = cipher_suite.decrypt(encrypted_text.encode('utf-8'))
    return decrypted_bytes.decode('utf-8')
