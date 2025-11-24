from sqlalchemy import (
    create_engine, Column, Integer, String, ForeignKey, DateTime, Enum as SQLEnum, Boolean, Text
)
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class UserRole(enum.Enum):
    ADMINISTRADOR = "administrador"
    SUPERVISOR = "supervisor"
    MONITOR = "monitor"
    TECNICO = "tecnico"
    AUTOSERVICIO = "autoservicio"

class TicketStatus(enum.Enum):
    NUEVO = "nuevo"
    ASIGNADO = "asignado"
    EN_PROCESO = "en_proceso"
    RESUELTO = "resuelto"
    CERRADO = "cerrado"
    RECHAZADO = "rechazado"

class TicketUrgency(enum.Enum):
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(100), unique=True, nullable=False)
    full_name = Column(String(255))
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False)
    location_id = Column(Integer, ForeignKey("locations.id"))
    phone = Column(String(50))
    is_active = Column(Integer, default=1)

    location = relationship("Location")
    # Relación a los tickets que este usuario ha solicitado (como cliente).
    requested_tickets = relationship("Ticket", foreign_keys="[Ticket.requester_id]", back_populates="requester")
    # Relación a los tickets que este usuario ha creado en el sistema (quien registra).
    created_tickets = relationship("Ticket", foreign_keys="[Ticket.creator_id]", back_populates="creator")
    assigned_tickets = relationship("Ticket", foreign_keys="[Ticket.technician_id]", back_populates="technician")

class Location(Base):
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(255))
    tickets = relationship("Ticket", back_populates="location")

class ITILCategory(Base):
    __tablename__ = "itil_categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    subcategories = relationship("ITILSubCategory", back_populates="category", cascade="all, delete-orphan")

class ITILSubCategory(Base):
    __tablename__ = "itil_subcategories"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    category_id = Column(Integer, ForeignKey("itil_categories.id"), nullable=False)
    category = relationship("ITILCategory", back_populates="subcategories")
    problem_types = relationship("ProblemType", back_populates="subcategory", cascade="all, delete-orphan")

class ProblemType(Base):
    __tablename__ = "problem_types"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    subcategory_id = Column(Integer, ForeignKey("itil_subcategories.id"), nullable=False)
    subcategory = relationship("ITILSubCategory", back_populates="problem_types")

class Ticket(Base):
    __tablename__ = "tickets"
    id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(SQLEnum(TicketStatus), default=TicketStatus.NUEVO)
    urgency = Column(SQLEnum(TicketUrgency), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    assigned_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))
    sla_warning_sent_level = Column(Integer, nullable=True) # Almacena el último nivel de advertencia SLA enviado (ej. 30, 15, 5 minutos).
    sla_violation_sent = Column(Boolean, default=False, nullable=False)

    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    technician_id = Column(Integer, ForeignKey("users.id"))
    problem_type_id = Column(Integer, ForeignKey("problem_types.id"))
    location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)

    requester = relationship("User", foreign_keys=[requester_id], back_populates="requested_tickets")
    creator = relationship("User", foreign_keys=[creator_id], back_populates="created_tickets")
    technician = relationship("User", foreign_keys=[technician_id], back_populates="assigned_tickets")
    problem_type = relationship("ProblemType")
    updates = relationship("TicketUpdate", back_populates="ticket", cascade="all, delete-orphan")
    location = relationship("Location", back_populates="tickets")

class TicketUpdate(Base):
    __tablename__ = "ticket_updates"
    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    comment = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    ticket = relationship("Ticket", back_populates="updates")
    author = relationship("User")

class SLA(Base):
    __tablename__ = "slas"
    id = Column(Integer, primary_key=True)
    urgency = Column(SQLEnum(TicketUrgency), unique=True, nullable=False)
    assignment_time_hours = Column(Integer, nullable=False)
    resolution_time_hours = Column(Integer, nullable=False)

class MailSettings(Base):
    __tablename__ = "mail_settings"
    id = Column(Integer, primary_key=True)
    server = Column(String(255))
    port = Column(Integer, default=993)
    email = Column(String(255))
    username = Column(String(255)) # El nombre de usuario para iniciar sesión, puede ser diferente al email.
    password = Column(String(512)) # Contraseña encriptada.
    use_ssl = Column(Integer, default=1)
    is_active = Column(Integer, default=0)
    check_interval_minutes = Column(Integer, default=5)
    smtp_server = Column(String(255))
    smtp_port = Column(Integer, default=587)
    smtp_use_ssl = Column(Integer, default=1)
