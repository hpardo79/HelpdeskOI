from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import joinedload
import asyncio
from database import SessionLocal
from models import Ticket, SLA, TicketStatus, UserRole, User
import notification_manager
import logging

# --- Configuración de Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)
# Umbrales de advertencia en minutos
WARNING_THRESHOLDS_MINUTES = [30, 15, 5]

async def check_sla_warnings():
    """
    Verifica los tickets activos y envía notificaciones de SLA según las reglas:
    - Advertencias a los 30, 15 y 5 minutos antes del vencimiento.
    - Notificación de violación de SLA si el tiempo ha expirado.
    - Dirige las notificaciones a los roles correspondientes (supervisores, monitores y técnico asignado).
    """
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        
        slas = {sla.urgency: sla for sla in db.query(SLA).all()}
        
        active_tickets = db.query(Ticket).options(
            joinedload(Ticket.technician),
            joinedload(Ticket.creator)
        ).filter(
            Ticket.status.in_([
                TicketStatus.NUEVO, 
                TicketStatus.ASIGNADO, 
                TicketStatus.EN_PROCESO
            ])
        ).all()

        logger.info(f"Verificando {len(active_tickets)} tickets activos...")

        # Roles a notificar siempre
        base_notification_roles = [UserRole.SUPERVISOR, UserRole.MONITOR]
        
        for ticket in active_tickets:
            if not ticket.urgency or ticket.urgency not in slas:
                continue

            sla = slas[ticket.urgency]
            sla_type, deadline = "", None

            # Determinar el tipo de SLA y su fecha límite
            if ticket.status == TicketStatus.NUEVO:
                sla_type = "asignación"
                deadline = ticket.created_at.replace(tzinfo=timezone.utc) + timedelta(hours=sla.assignment_time_hours)
            elif ticket.status in [TicketStatus.ASIGNADO, TicketStatus.EN_PROCESO] and ticket.assigned_at:
                sla_type = "resolución"
                deadline = ticket.assigned_at.replace(tzinfo=timezone.utc) + timedelta(hours=sla.resolution_time_hours)
            else:
                continue

            time_left = deadline - now

            # --- Lógica de Violación ---
            if time_left <= timedelta(0):
                if not ticket.sla_violation_sent:
                    overdue = -time_left
                    h, m = divmod(overdue.total_seconds() / 60, 60)
                    time_info = f"{int(h)}h {int(m)}m" # Formato para el correo
                    print(f"Ticket #{ticket.id}: VIOLACIÓN de SLA de {sla_type}. Excedido por {time_info}.")
                    
                    recipients = db.query(User).filter(User.role.in_(base_notification_roles), User.is_active == 1).all()
                    if ticket.technician:
                        recipients.append(ticket.technician)

                    notification_manager.notify_sla_event(ticket, "VIOLACIÓN", sla_type, time_info, list(set(recipients)))
                    ticket.sla_violation_sent = True
                    db.add(ticket)
                continue # No enviar advertencias si ya está violado

            # --- Lógica de Advertencias por Vencimiento ---
            # Determinar el umbral de advertencia actual basado en el tiempo restante
            current_warning_level = 0
            for threshold in WARNING_THRESHOLDS_MINUTES:
                if time_left <= timedelta(minutes=threshold):
                    current_warning_level = threshold
                    break
            
            # Si estamos en un nivel de advertencia y no se ha enviado una para este nivel o uno superior
            if current_warning_level > 0 and (ticket.sla_warning_sent_level is None or current_warning_level < ticket.sla_warning_sent_level):
                time_info = f"{current_warning_level} minutos"
                logger.warning(f"Ticket #{ticket.id}: ADVERTENCIA de SLA de {sla_type}. Restan aprox. {time_info}.")

                # Definir destinatarios según el estado del ticket
                recipients_query = db.query(User).filter(User.role.in_(base_notification_roles), User.is_active == 1)
                recipients = recipients_query.all()
                if ticket.technician: # Si está asignado, añadir al técnico
                    recipients.append(ticket.technician)
                
                notification_manager.notify_sla_event(ticket, "ADVERTENCIA", sla_type, time_info, list(set(recipients)))
                ticket.sla_warning_sent_level = current_warning_level
                db.add(ticket)

        db.commit()

    except Exception as e:
        logger.error(f"Error en el verificador de SLA: {e}")
        db.rollback()
    finally:
        db.close()