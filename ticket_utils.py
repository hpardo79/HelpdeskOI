from nicegui import app
from sqlalchemy.orm import joinedload
from sqlalchemy import func

from database import SessionLocal
from models import Ticket, User, UserRole, TicketUrgency
from datetime_utils import to_local_time

def load_tickets(status=None, urgency=None, technician_id=None, search_term=None):
    """
    Carga los tickets desde la base de datos, aplicando filtros opcionales.
    También aplica filtros de visibilidad según el rol del usuario (técnicos, autoservicio, etc.).
    """
    db = SessionLocal()
    try:
        role = app.storage.user.get('role')
        user = db.query(User).filter(User.username == app.storage.user.get('username')).first()
        if not user:
            return []

        query = db.query(Ticket).options(
            joinedload(Ticket.creator),
            joinedload(Ticket.requester),
            joinedload(Ticket.technician),
            joinedload(Ticket.problem_type),
            joinedload(Ticket.location)
        ).order_by(Ticket.created_at.desc())

        # Aplicar filtro de visibilidad por rol
        if role == UserRole.TECNICO.value:
            query = query.filter(Ticket.technician_id == user.id)
        elif role == UserRole.AUTOSERVICIO.value:
            query = query.filter(Ticket.creator_id == user.id)
        
        if status:
            query = query.filter(Ticket.status == status)
        if urgency:
            query = query.filter(Ticket.urgency == urgency)
        if technician_id:
            query = query.filter(Ticket.technician_id == technician_id)
        if search_term:
            query = query.filter(Ticket.title.ilike(f'%{search_term}%'))

        tickets = query.all()
        
        return [{
            'id': t.id,
            'title': t.title,
            'description': t.description,
            'status': t.status.value,
            'urgency': t.urgency.value if t.urgency else 'Sin clasificar',
            'requester_name': t.requester.username if t.requester else 'N/A',
            'technician_name': t.technician.username if t.technician else 'Sin asignar',
            'location_name': t.location.description if t.location else 'Sin especificar',
            'created_at': to_local_time(t.created_at),
        } for t in tickets]
    finally:
        db.close()
