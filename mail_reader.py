import imaplib
import email
from email.header import decode_header
import asyncio
import logging
import secrets
import string
import socket
import time
from datetime import datetime, timezone

from database import SessionLocal, get_password_hash
from models import User, Ticket, TicketStatus, TicketUrgency, ProblemType, MailSettings, UserRole
from crypto_utils import decrypt_text

# --- Constantes para la lógica de reintentos de conexión ---
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 30

# --- Configuración de Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def get_body(msg):
    """Extrae el cuerpo del mensaje de correo electrónico."""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == 'text/plain' and 'attachment' not in content_disposition:
                return part.get_payload(decode=True).decode('utf-8', errors='ignore')
    else:
        return msg.get_payload(decode=True).decode('utf-8', errors='ignore')
    return ""

async def generate_random_password(length=16):
    """Genera una contraseña aleatoria segura."""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for i in range(length))

async def check_new_emails():
    """
    Se conecta al servidor IMAP, busca correos no leídos y crea tickets.
    Si el remitente no existe, crea un nuevo usuario de autoservicio.
    """
    logger.info("Iniciando revisión de correos electrónicos...") # Log de inicio

    db = SessionLocal()
    try:
        settings = db.query(MailSettings).first()

        if not settings or not settings.is_active:
            # logger.info("El lector de correos está desactivado o no configurado. Omitiendo revisión.")
            return

        mail = None
        for attempt in range(MAX_RETRIES):
            try:
                decrypted_password = decrypt_text(settings.password)
                
                logger.info(f"Intento de conexión IMAP {attempt + 1}/{MAX_RETRIES} a {settings.server}...")
                # Usar la configuración de conexión (SSL/TLS o no)
                if settings.use_ssl:
                    mail = imaplib.IMAP4_SSL(settings.server, settings.port)
                else:
                    mail = imaplib.IMAP4(settings.server, settings.port)

                login_user = settings.username if settings.username else settings.email
                mail.login(login_user, decrypted_password)
                logger.info("Conexión IMAP exitosa.")
                break  # Si la conexión es exitosa, salimos del bucle de reintentos
            
            except (socket.gaierror, imaplib.IMAP4.error) as e:
                logger.warning(f"Fallo en el intento {attempt + 1}: {e}")
                if attempt < MAX_RETRIES - 1:
                    logger.info(f"Reintentando en {RETRY_DELAY_SECONDS} segundos...")
                    await asyncio.sleep(RETRY_DELAY_SECONDS)
                else:
                    logger.error("Se alcanzó el número máximo de reintentos. Abortando la revisión de correos.")
                    return
        
        if not mail:
            return # No se pudo establecer la conexión

        try:
            mail.select('inbox')
            status, messages = mail.search(None, 'UNSEEN')
            if status != 'OK':
                logger.error("No se pudieron buscar correos.")
                mail.logout()
                return

            email_ids = messages[0].split()
            if email_ids and email_ids[0]:
                logger.info(f"Se encontraron {len(email_ids)} correos nuevos.")

                for email_id in email_ids:
                    res, msg_data = mail.fetch(email_id, '(RFC822)')
                    if res != 'OK':
                        logger.error(f"No se pudo obtener el correo ID {email_id}")
                        continue

                    msg = email.message_from_bytes(msg_data[0][1])

                    subject, encoding = decode_header(msg['Subject'])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding or 'utf-8')

                    # Filtrar correos por asunto para crear tickets solo si cumplen la condición
                    normalized_subject = subject.lower().strip()
                    if not (normalized_subject.startswith('reporte') or normalized_subject.startswith('report')):
                        logger.info(f'Asunto "{subject}" no coincide con el filtro ("Reporte" o "Report"). Ignorando y marcando como leído.')
                        # Marcar el correo como leído para no volver a procesarlo
                        mail.store(email_id, '+FLAGS', r'\Seen')
                        continue

                    from_address = email.utils.parseaddr(msg['From'])[1]
                    
                    logger.info(f'Procesando correo de <{from_address}> con asunto: "{subject}"')

                    user = db.query(User).filter(User.email == from_address).first()

                    if not user:
                        logger.warning(f"Usuario con email <{from_address}> no encontrado. Creando nuevo usuario de autoservicio.")
                        try:
                            username = from_address
                            random_password = await generate_random_password()
                            password_hash = get_password_hash(random_password)

                            new_user = User(
                                username=username,
                                email=from_address,
                                full_name="Usuario Creado por Email",
                                password_hash=password_hash,
                                role=UserRole.AUTOSERVICIO,
                                is_active=1
                            )
                            db.add(new_user)
                            db.commit()
                            db.refresh(new_user)
                            logger.info(f"Nuevo usuario de autoservicio creado con ID: {new_user.id} y email: {from_address}")
                            user = new_user
                        except Exception as e:
                            logger.error(f"No se pudo crear el nuevo usuario para el email <{from_address}>: {e}")
                            db.rollback()
                            mail.store(email_id, '+FLAGS', r'\Seen')
                            continue

                    body = get_body(msg)
                    if not body:
                        logger.warning("El correo no tiene un cuerpo de texto plano. Ignorando.")
                        mail.store(email_id, '+FLAGS', r'\Seen')
                        continue

                    try:
                        new_ticket = Ticket(
                            title=subject or "(Sin Asunto)",
                            description=body,
                            requester_id=user.id,
                            creator_id=user.id,
                            created_at=datetime.now(timezone.utc),
                            status=TicketStatus.NUEVO,
                            urgency=None,
                            problem_type_id=None
                        )
                        db.add(new_ticket)
                        db.commit()
                        logger.info(f"Ticket #{new_ticket.id} creado exitosamente para el usuario {user.username} (pendiente de clasificación).")
                        
                        mail.store(email_id, '+FLAGS', r'\Seen')

                    except Exception as e:
                        logger.error(f"Error al crear el ticket en la BD para el correo de <{from_address}>: {e}")
                        db.rollback()

            mail.logout()
        except Exception as e:
            logger.error(f"Error inesperado durante el procesamiento de correos: {e}")

    finally:
        db.close()

if __name__ == '__main__':
    print("Ejecutando el lector de correos de forma manual...")
    check_new_emails()
    print("Proceso finalizado.")
