import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from database import SessionLocal
from models import MailSettings
from crypto_utils import decrypt_text

def send_email_notification(recipient_email: str, subject: str, body: str):
    db = SessionLocal()
    try:
        settings = db.query(MailSettings).first()
        if not settings or not settings.smtp_server or not settings.is_active:
            print(f"WARN: SMTP settings are not configured or inactive. Email to {recipient_email} was not sent.")
            return

        sender_email = settings.email
        password = decrypt_text(settings.password)
        
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = f"HelpdeskOI <{sender_email}>"
        message["To"] = recipient_email

        # El cuerpo del correo es HTML, generado desde `notification_templates`.
        part = MIMEText(body, "html")
        message.attach(part)

        context = ssl.create_default_context()
        
        try:
            login_user = settings.username if settings.username else sender_email
            
            if settings.smtp_use_ssl:
                with smtplib.SMTP_SSL(settings.smtp_server, settings.smtp_port, context=context) as server:
                    server.login(login_user, password)
                    server.sendmail(sender_email, recipient_email, message.as_string())
            else: # Usar STARTTLS
                with smtplib.SMTP(settings.smtp_server, settings.smtp_port) as server:
                    server.starttls(context=context)
                    server.login(login_user, password)
                    server.sendmail(sender_email, recipient_email, message.as_string())
            
            print(f"Notification email sent to {recipient_email}")

        except Exception as e:
            print(f"ERROR: Could not send email to {recipient_email}. Reason: {e}")

    finally:
        db.close()