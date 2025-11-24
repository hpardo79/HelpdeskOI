
from database import SessionLocal, verify_password
from models import User

def authenticate_user(username: str, password: str) -> User | None:
    """
    Verifica las credenciales de un usuario contra la base de datos.
    Retorna el objeto `User` si la autenticación es exitosa, o `None` si falla.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user
    finally:
        db.close()
