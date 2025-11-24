def get_base_template(content: str) -> str:
    """Crea la estructura HTML base para todos los correos de notificación."""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background-color: #f4f4f4; }}
            .container {{ width: 100%; max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 20px; }}
            .header {{ background-color: #007bff; color: #ffffff; padding: 10px; text-align: center; }}
            .content {{ padding: 20px; }}
            .footer {{ font-size: 0.8em; text-align: center; color: #777; padding: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>HelpdeskOI</h1>
            </div>
            <div class="content">
                {content}
            </div>
            <div class="footer">
                <p>Este es un correo generado automáticamente. Por favor, no responda a este mensaje.</p>
            </div>
        </div>
    </body>
    </html>
    """

def new_ticket_notification(ticket_id: int, title: str, creator_name: str) -> str:
    """Genera el correo de notificación para un nuevo ticket."""
    body = f"""
    <h2>Nuevo Ticket Creado: #{ticket_id}</h2>
    <p>Hola,</p>
    <p>Se ha creado un nuevo ticket en el sistema HelpdeskOI.</p>
    <ul>
        <li><b>ID del Ticket:</b> {ticket_id}</li>
        <li><b>Título:</b> {title}</li>
        <li><b>Creado por:</b> {creator_name}</li>
    </ul>
    <p>Puedes ver los detalles del ticket en el sistema.</p>
    """
    return get_base_template(body)

def ticket_assigned_notification(ticket_id: int, title: str, technician_name: str) -> str:
    """Genera el correo de notificación para un ticket que ha sido asignado."""
    body = f"""
    <h2>Ticket Asignado: #{ticket_id}</h2>
    <p>Hola {technician_name},</p>
    <p>Se te ha asignado el siguiente ticket:</p>
    <ul>
        <li><b>ID del Ticket:</b> {ticket_id}</li>
        <li><b>Título:</b> {title}</li>
    </ul>
    <p>Por favor, revisa los detalles en el dashboard de HelpdeskOI.</p>
    """
    return get_base_template(body)

def ticket_update_notification(ticket_id: int, title: str, author_name: str, comment: str) -> str:
    """Genera el correo para una actualización o comentario en un ticket."""
    body = f"""
    <h2>Actualización en el Ticket: #{ticket_id}</h2>
    <p>Hola,</p>
    <p>El ticket "{title}" ha sido actualizado por <b>{author_name}</b>.</p>
    <p><b>Comentario:</b></p>
    <blockquote style="border-left: 2px solid #ccc; padding-left: 10px; margin-left: 5px;">
        {comment}
    </blockquote>
    <p>Puedes ver los detalles del ticket en el sistema.</p>
    """
    return get_base_template(body)

def ticket_status_change_notification(ticket_id: int, title: str, new_status: str) -> str:
    """Genera el correo para un cambio de estado en un ticket."""
    body = f"""
    <h2>Cambio de Estado en el Ticket: #{ticket_id}</h2>
    <p>Hola,</p>
    <p>El estado del ticket "{title}" ha cambiado a: <b>{new_status}</b>.</p>
    <p>Puedes ver los detalles del ticket en el sistema.</p>
    """
    return get_base_template(body)

def sla_warning_notification(ticket_id: int, title: str, technician_name: str, notification_type: str, time_left: str) -> str:
    """Genera el correo de advertencia por vencimiento de SLA."""
    body = f"""
    <h2>Advertencia de Vencimiento de SLA para el Ticket #{ticket_id}</h2>
    <p>Hola {technician_name},</p>
    <p>
        Este es un aviso de que el ticket <b>#{ticket_id}: "{title}"</b> está a punto de vencer su
        tiempo de <b>{notification_type}</b> establecido por el SLA.
    </p>
    <p>
        Tiempo restante aproximado: <b>{time_left}</b>
    </p>
    <p>Por favor, toma las acciones necesarias a la brevedad.</p>
    """
    return get_base_template(body)

def sla_violation_notification(ticket_id: int, title: str, technician_name: str, notification_type: str, overdue_time: str) -> str:
    """Genera el correo de notificación por violación de SLA."""
    body = f"""
    <h2>¡VIOLACIÓN DE SLA para el Ticket #{ticket_id}!</h2>
    <p>Hola {technician_name},</p>
    <p>
        El ticket <b>#{ticket_id}: "{title}"</b> ha violado su tiempo de <b>{notification_type}</b>
        establecido por el SLA.
    </p>
    <p>
        Tiempo excedido: <b>{overdue_time}</b>
    </p>
    <p>Por favor, toma las acciones correctivas necesarias de inmediato.</p>
    """
    return get_base_template(body)
