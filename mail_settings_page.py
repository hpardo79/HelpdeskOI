from nicegui import app, ui
import imaplib
import smtplib
import ssl
import socket

from database import SessionLocal
from models import MailSettings
from crypto_utils import encrypt_text, decrypt_text
from main_layout import create_main_layout

@ui.page('/admin/mail_settings')
def admin_mail_settings():
    if not app.storage.user.get('authenticated', False) or app.storage.user.get('role') != 'administrador':
        return ui.navigate.to('/')

    db = SessionLocal()
    settings = db.query(MailSettings).first()
    db.close()

    async def test_imap_connection():
        """Prueba la conexión con el servidor IMAP."""
        ui.notify("Probando conexión IMAP...", timeout=2000)
        pwd = password_input.value
        if not pwd and settings and settings.password:
            pwd = decrypt_text(settings.password)

        if not all([imap_server_input.value, imap_port_input.value, email_input.value, pwd]):
            ui.notify("Faltan datos de IMAP para realizar la prueba.", color='warning')
            return

        try:
            login_user = username_input.value if username_input.value else email_input.value
            if imap_ssl_switch.value:
                mail = imaplib.IMAP4_SSL(imap_server_input.value, int(imap_port_input.value))
            else:
                mail = imaplib.IMAP4(imap_server_input.value, int(imap_port_input.value))
            mail.login(login_user, pwd)
            mail.logout()
            ui.notify("¡Conexión IMAP exitosa!", color='positive')
        except socket.gaierror:
            ui.notify(f"Error de Red IMAP: No se pudo resolver el servidor '{imap_server_input.value}'.", color='negative')
        except imaplib.IMAP4.error as e:
            ui.notify(f"Error de Autenticación IMAP: {e}", color='negative')
        except Exception as e:
            ui.notify(f"Error inesperado en IMAP: {e}", color='negative')

    async def test_smtp_connection():
        """Prueba la conexión con el servidor SMTP."""
        ui.notify("Probando conexión SMTP...", timeout=2000)
        pwd = password_input.value
        if not pwd and settings and settings.password:
            pwd = decrypt_text(settings.password)

        if not all([smtp_server_input.value, smtp_port_input.value, email_input.value, pwd]):
            ui.notify("Faltan datos de SMTP para realizar la prueba.", color='warning')
            return

        try:
            login_user = username_input.value if username_input.value else email_input.value
            context = ssl.create_default_context()
            
            if smtp_ssl_switch.value:
                with smtplib.SMTP_SSL(smtp_server_input.value, int(smtp_port_input.value), context=context) as server:
                    server.login(login_user, pwd)
            else:
                with smtplib.SMTP(smtp_server_input.value, int(smtp_port_input.value)) as server:
                    server.starttls(context=context)
                    server.login(login_user, pwd)
            
            ui.notify("¡Conexión SMTP exitosa!", color='positive')
        except smtplib.SMTPAuthenticationError as e:
            ui.notify(f"Error de Autenticación SMTP: {e}", color='negative', multi_line=True)
        except socket.gaierror:
            ui.notify(f"Error de Red SMTP: No se pudo resolver el servidor '{smtp_server_input.value}'.", color='negative')
        except Exception as e:
            ui.notify(f"Error inesperado en SMTP: {e}", color='negative', multi_line=True)

    async def run_connection_tests():
        await test_imap_connection()
        await test_smtp_connection()

    def save_settings():
        db = SessionLocal()
        try:
            current_settings = db.query(MailSettings).first()
            if not current_settings:
                current_settings = MailSettings(id=1)
                db.add(current_settings)

            current_settings.server = imap_server_input.value
            current_settings.port = int(imap_port_input.value)
            current_settings.use_ssl = 1 if imap_ssl_switch.value else 0
            current_settings.smtp_server = smtp_server_input.value
            current_settings.smtp_port = int(smtp_port_input.value)
            current_settings.smtp_use_ssl = 1 if smtp_ssl_switch.value else 0
            current_settings.email = email_input.value
            current_settings.username = username_input.value
            current_settings.is_active = 1 if active_switch.value else 0
            current_settings.check_interval_minutes = int(interval_input.value)

            if password_input.value:
                current_settings.password = encrypt_text(password_input.value)

            db.commit()
            ui.notify("Configuración de correo guardada. La aplicación se reiniciará para aplicar los cambios.", color='positive', multi_line=True)
            
            # Programar el apagado para permitir que la notificación se envíe primero.
            ui.timer(1.0, app.shutdown, once=True)
        except Exception as e:
            db.rollback()
            ui.notify(f"Error al guardar la configuración: {e}", color='negative')
        finally:
            db.close()

    create_main_layout()
    with ui.column().classes('w-full p-4 md:p-6 lg:p-8 gap-6'):
        with ui.card().classes('w-full rounded-xl shadow-md'):
            with ui.card_section().classes('bg-gray-100'):
                ui.label("Configuración de Correo").classes('text-2xl font-bold text-gray-800 text-center p-4')
            
            with ui.column().classes('p-6 gap-6'):
                with ui.card().classes('w-full border'):
                    with ui.card_section():
                        ui.label("Configuración General del Servicio").classes('text-xl font-semibold text-gray-700')
                    ui.separator()
                    with ui.column().classes('p-4 gap-4'):
                        active_switch = ui.switch("Activar servicio de correo (lectura y envío)", value=bool(settings.is_active) if settings else False)
                        interval_input = ui.number("Intervalo de revisión de correo (minutos)", value=settings.check_interval_minutes if settings else 5, min=1).props('filled')

                with ui.card().classes('w-full border'):
                    with ui.card_section():
                        ui.label("Credenciales Comunes").classes('text-xl font-semibold text-gray-700')
                    ui.separator()
                    with ui.column().classes('p-4 gap-4'):
                        email_input = ui.input("Email de la cuenta", value=settings.email if settings else '').props('filled')
                        username_input = ui.input("Nombre de Usuario (si es diferente al email)", value=settings.username if settings else '').props('filled')
                        password_input = ui.input("Contraseña", password=True).props('filled').classes('w-full').tooltip("Dejar en blanco para no cambiar la contraseña actual.")

                with ui.card().classes('w-full border'):
                    with ui.card_section():
                        ui.label("Configuración de Lectura (IMAP)").classes('text-xl font-semibold text-gray-700')
                        ui.label("Configure la cuenta que el sistema usará para crear tickets desde emails.").classes('text-gray-600 text-sm')
                    ui.separator()
                    with ui.column().classes('p-4 gap-4'):
                        with ui.row().classes('w-full grid grid-cols-1 md:grid-cols-2 gap-6'):
                            imap_server_input = ui.input("Servidor IMAP", value=settings.server if settings else 'imap.example.com').props('filled')
                            imap_port_input = ui.number("Puerto IMAP", value=settings.port if settings else 993).props('filled')
                        imap_ssl_switch = ui.switch("Usar SSL/TLS para IMAP", value=bool(settings.use_ssl) if settings else True)

                with ui.card().classes('w-full border'):
                    with ui.card_section():
                        ui.label("Configuración de Envío (SMTP)").classes('text-xl font-semibold text-gray-700')
                        ui.label("Configure la cuenta que el sistema usará para enviar notificaciones.").classes('text-gray-600 text-sm')
                    ui.separator()
                    with ui.column().classes('p-4 gap-4'):
                        with ui.row().classes('w-full grid grid-cols-1 md:grid-cols-2 gap-6'):
                            smtp_server_input = ui.input("Servidor SMTP", value=settings.smtp_server if settings else 'smtp.example.com').props('filled')
                            smtp_port_input = ui.number("Puerto SMTP", value=settings.smtp_port if settings else 587).props('filled')
                        smtp_ssl_switch = ui.switch("Usar SSL/TLS para SMTP", value=bool(settings.smtp_use_ssl) if settings else True)

            with ui.row().classes('w-full justify-end gap-2 p-4 bg-gray-100 mt-4'):
                ui.button("Probar Conexiones (IMAP & SMTP)", on_click=run_connection_tests, icon='sync').props('outline')
                ui.button("Guardar Configuración", on_click=save_settings, color='primary', icon='save')