from asyncio import get_running_loop
from database import SessionLocal
from models import Ticket, User, TicketUpdate
from email_utils import send_email_notification
import notification_templates as nt


def _send_email_in_background(to_address: str, subject: str, html_content: str):
    """Ejecuta el envío de correo en un hilo separado para no bloquear la interfaz."""
    if not to_address:
        print(f"WARN: No email address for notification with subject: {subject}")
        return
    loop = get_running_loop()
    loop.run_in_executor(None, send_email_notification, to_address, subject, html_content)


def notify_new_ticket(ticket: Ticket):
    """Notifica al creador sobre un nuevo ticket."""
    if ticket.creator and ticket.creator.email:
        subject = f"Ticket #{ticket.id} Creado: {ticket.title}"
        html_content = nt.new_ticket_notification(
            ticket_id=ticket.id,
            title=ticket.title,
            creator_name=ticket.creator.username
        )
        _send_email_in_background(ticket.creator.email, subject, html_content)


def notify_ticket_assigned(ticket: Ticket, assigner: User):
    """Notifica al técnico asignado y al creador."""
    # 1. Notificar al técnico
    if ticket.technician and ticket.technician.email:
        subject = f"Nuevo Ticket Asignado #{ticket.id}: {ticket.title}"
        html_content = nt.ticket_assigned_notification(
            ticket_id=ticket.id,
            title=ticket.title,
            technician_name=ticket.technician.username
        )
        _send_email_in_background(ticket.technician.email, subject, html_content)

    # 2. Notificar al solicitante
    if ticket.creator and ticket.creator.email:
        subject = f"Actualización en tu Ticket #{ticket.id}"
        comment = f"El ticket ha sido asignado al técnico {ticket.technician.username}."
        html_content = nt.ticket_update_notification(
            ticket_id=ticket.id,
            title=ticket.title,
            author_name=assigner.username,
            comment=comment
        )
        _send_email_in_background(ticket.creator.email, subject, html_content)


def notify_ticket_update(ticket: Ticket, update: TicketUpdate):
    """Notifica al creador y/o técnico sobre una actualización."""
    # 1. Notificar al creador (si no es quien actualiza)
    if ticket.creator and ticket.creator.email and ticket.creator_id != update.author_id:
        subject = f"Actualización en tu Ticket #{ticket.id}"
        html_content = nt.ticket_update_notification(
            ticket_id=ticket.id,
            title=ticket.title,
            author_name=update.author.username,
            comment=update.comment
        )
        _send_email_in_background(ticket.creator.email, subject, html_content)

    # 2. Notificar al técnico (si no es quien actualiza)
    if ticket.technician and ticket.technician.email and ticket.technician_id != update.author_id:
        subject = f"Actualización en Ticket Asignado #{ticket.id}"
        html_content = nt.ticket_update_notification(
            ticket_id=ticket.id,
            title=ticket.title,
            author_name=update.author.username,
            comment=update.comment
        )
        _send_email_in_background(ticket.technician.email, subject, html_content)


def notify_status_change(ticket: Ticket, old_status: str, author: User):
    """Notifica al creador sobre un cambio de estado."""
    if ticket.creator and ticket.creator.email:
        subject = f"Cambio de Estado en tu Ticket #{ticket.id}"
        comment = f"El estado del ticket ha cambiado de '{old_status}' a '{ticket.status.value}'."
        html_content = nt.ticket_update_notification(
            ticket_id=ticket.id,
            title=ticket.title,
            author_name=author.username,
            comment=comment
        )
        _send_email_in_background(ticket.creator.email, subject, html_content)


def notify_reassignment(ticket: Ticket, old_technician: User, assigner: User):
    """Notifica al nuevo técnico, al anterior y al creador sobre una reasignación."""
    # Notificar al nuevo técnico
    if ticket.technician and ticket.technician.email:
        subject = f"Nuevo Ticket Asignado #{ticket.id}: {ticket.title}"
        html_content = nt.ticket_assigned_notification(ticket.id, ticket.title, ticket.technician.username)
        _send_email_in_background(ticket.technician.email, subject, html_content)

    # Notificar al técnico anterior
    if old_technician and old_technician.email:
        subject = f"Ticket Reasignado #{ticket.id}: {ticket.title}"
        comment = f"El ticket que tenías asignado ha sido reasignado a {ticket.technician.username} por {assigner.username}."
        html_content = nt.ticket_update_notification(ticket.id, ticket.title, assigner.username, comment)
        _send_email_in_background(old_technician.email, subject, html_content)

    # Notificar al creador
    if ticket.creator and ticket.creator.email:
        subject = f"Actualización en tu Ticket #{ticket.id}"
        comment = f"El ticket ha sido reasignado al técnico {ticket.technician.username}."
        html_content = nt.ticket_update_notification(ticket.id, ticket.title, assigner.username, comment)
        _send_email_in_background(ticket.creator.email, subject, html_content)

def notify_sla_event(ticket: Ticket, event_type: str, sla_type: str, time_info: str, recipients: list[User]):
    """
    Notifica a los destinatarios correctos sobre un evento de SLA (advertencia o violación).

    Args:
        ticket: El ticket afectado.
        event_type: 'ADVERTENCIA' o 'VIOLACIÓN'.
        sla_type: 'asignación' o 'resolución'.
        time_info: El tiempo restante o excedido (ej. "25 minutos").
        recipients: Lista de usuarios a notificar.
    """
    if not recipients:
        print(f"WARN: No hay destinatarios para la notificación de SLA ({event_type}) del ticket #{ticket.id}")
        return

    subject = f"[{event_type}] SLA de {sla_type} para Ticket #{ticket.id}: {ticket.title}"

    for user in recipients:
        if not user.email:
            continue

        if event_type == "ADVERTENCIA":
            html_content = nt.sla_warning_notification(
                ticket_id=ticket.id,
                title=ticket.title,
                technician_name=user.username,
                notification_type=sla_type,
                time_left=time_info
            )
        else: # VIOLACIÓN
            html_content = nt.sla_violation_notification(
                ticket_id=ticket.id,
                title=ticket.title,
                technician_name=user.username,
                notification_type=sla_type,
                overdue_time=time_info
            )
        
        _send_email_in_background(user.email, subject, html_content)