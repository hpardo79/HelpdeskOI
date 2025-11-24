from dotenv import load_dotenv
from nicegui import app, ui, run
import asyncio

load_dotenv()  # Carga las variables de entorno desde el archivo .env
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from datetime import datetime, timezone
import imaplib
import socket
import os

from database import init_db, SessionLocal
from models import Ticket, User, ProblemType, UserRole, TicketUrgency, TicketStatus, TicketUpdate, SLA, MailSettings, ITILCategory, ITILSubCategory, Location
from auth import authenticate_user
from datetime_utils import to_local_time, format_utc_time
from main_layout import create_main_layout
from mail_reader import check_new_emails
from sla_checker import check_sla_warnings
from crypto_utils import encrypt_text

import notification_manager as notifier
from search import search_page
import dashboard
import mail_settings_page
import reports_page

# --- PÁGINAS DE LA APLICACIÓN ---

@ui.page('/')
def main_page():
    """Página principal que redirige al login o al dashboard."""
    if not app.storage.user.get('authenticated', False):
        show_login()
    else:
        ui.navigate.to('/dashboard')



@ui.page('/ticket/{ticket_id}')
def show_ticket_details(ticket_id: int):
    """Muestra los detalles de un ticket específico."""
    if not app.storage.user.get('authenticated', False):
        return ui.navigate.to('/')

    create_main_layout()
    main_container = ui.column().classes('w-full')

    def build_ticket_view():
        """Construye o reconstruye toda la interfaz de la página de detalles del ticket."""
        main_container.clear()
        with main_container:
            # --- Lógica de Acciones ---
            # Se definen aquí para que tengan acceso a las variables de la vista que se está construyendo.
            def handle_details_update(new_title, new_description):
                db = SessionLocal()
                try:
                    ticket_to_update = db.query(Ticket).options(joinedload(Ticket.creator), joinedload(Ticket.technician)).filter(Ticket.id == ticket_id).first()
                    if not ticket_to_update: return ui.notify("El ticket no fue encontrado.", color='negative')
                    current_user = db.query(User).filter(User.username == app.storage.user.get('username')).first()
                    if not current_user: return ui.notify("No se pudo identificar al usuario.", color='negative')

                    update_comments = []
                    if new_title != ticket_to_update.title:
                        update_comments.append(f"Título actualizado a: '{new_title}'.")
                        ticket_to_update.title = new_title
                    if new_description != ticket_to_update.description:
                        update_comments.append("Descripción actualizada.")
                        ticket_to_update.description = new_description
                    
                    if update_comments:
                        update = TicketUpdate(ticket_id=ticket_id, author_id=current_user.id, comment="\n".join(update_comments))
                        db.add(update)
                        db.commit()
                        ui.notify("Ticket actualizado.", color='positive') # Notificar al usuario
                        notifier.notify_ticket_update(ticket_to_update, update)
                        build_ticket_view() # Refrescar vista
                    else:
                        ui.notify("No hay cambios para guardar.", color='info')
                except Exception as e:
                    db.rollback()
                    ui.notify(f"Error al actualizar: {e}", color='negative')
                finally:
                    db.close()

            def assign_ticket(technician_id):
                db = SessionLocal()
                try:
                    ticket_to_update = db.query(Ticket).options(joinedload(Ticket.technician), joinedload(Ticket.creator)).filter(Ticket.id == ticket_id).first()
                    if not ticket_to_update: return ui.notify("Ticket no encontrado.", color='negative')

                    tech_user = db.query(User).filter(User.id == technician_id).first()
                    current_user = db.query(User).filter(User.username == app.storage.user.get('username')).first()

                    ticket_to_update.technician_id = technician_id
                    ticket_to_update.status = TicketStatus.ASIGNADO
                    ticket_to_update.assigned_at = datetime.now(timezone.utc)
                    
                    update = TicketUpdate(ticket_id=ticket_id, author_id=current_user.id, comment=f"Ticket asignado a {tech_user.username}.")
                    db.add(update)
                    db.commit()

                    ui.notify("Ticket asignado correctamente", color='positive')
                    notifier.notify_ticket_assigned(ticket_to_update, current_user)
                    build_ticket_view() # Refrescar la vista
                except Exception as e:
                    db.rollback()
                    ui.notify(f"Error al asignar ticket: {e}", color='negative')
                finally:
                    db.close()

            async def reject_ticket():
                with ui.dialog() as dialog, ui.card().classes('rounded-lg'):
                    ui.label("Rechazar Ticket").classes('text-lg font-semibold p-4')
                    with ui.column().classes('p-4 gap-4'):
                        reason_input = ui.textarea().props("filled label='Motivo del rechazo'").classes('w-full')
                    with ui.row().classes('w-full justify-end gap-2 p-4'):
                        ui.button("Confirmar Rechazo", on_click=lambda: dialog.submit(reason_input.value), color='negative')
                        ui.button("Cancelar", on_click=dialog.close)
                
                reason = await dialog
                if reason:
                    db = SessionLocal()
                    try:
                        ticket_to_update = db.query(Ticket).options(joinedload(Ticket.creator)).filter(Ticket.id == ticket_id).first()
                        if not ticket_to_update: return ui.notify("Ticket no encontrado.", color='negative')

                        current_user = db.query(User).filter(User.username == app.storage.user.get('username')).first()
                        
                        ticket_to_update.status = TicketStatus.RECHAZADO
                        update = TicketUpdate(ticket_id=ticket_id, author_id=current_user.id, comment=f"Ticket Rechazado. Motivo: {reason}")
                        db.add(update)
                        db.commit()
                        db.refresh(update)
                        
                        ui.notify("Ticket rechazado.", color='positive')
                        notifier.notify_ticket_update(ticket_to_update, update)
                        build_ticket_view() # Refrescar la vista
                    except Exception as e:
                        db.rollback()
                        ui.notify(f"Error al rechazar ticket: {e}", color='negative')
                    finally:
                        db.close()

            async def reassign_ticket():
                db = SessionLocal()
                try:
                    current_ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
                    technicians = db.query(User).filter(User.role == UserRole.TECNICO, User.is_active == 1, User.id != current_ticket.technician_id).all()
                    tech_options = {t.id: t.username for t in technicians}
                finally:
                    db.close()

                with ui.dialog() as dialog, ui.card().classes('rounded-lg'):
                    ui.label("Reasignar Ticket").classes('text-lg font-semibold p-4')
                    with ui.column().classes('p-4 gap-4'):
                        tech_select = ui.select(tech_options, label="Seleccionar Nuevo Técnico").props("filled")
                        reason_input = ui.textarea().props("filled label='Motivo de la reasignación'").classes('w-full')
                    with ui.row().classes('w-full justify-end gap-2 p-4'):
                        ui.button("Confirmar", on_click=lambda: dialog.submit((tech_select.value, reason_input.value)), color='primary')
                        ui.button("Cancelar", on_click=dialog.close)
                
                result = await dialog
                if result:
                    new_tech_id, reason = result
                    if not all([new_tech_id, reason]): return ui.notify("Debe seleccionar un técnico y un motivo.", color='warning')
                    
                    db = SessionLocal()
                    try:
                        ticket_to_update = db.query(Ticket).options(joinedload(Ticket.creator), joinedload(Ticket.technician)).filter(Ticket.id == ticket_id).first()
                        if not ticket_to_update: return ui.notify("Ticket no encontrado.", color='negative')

                        old_technician = ticket_to_update.technician
                        new_tech_user = db.query(User).filter(User.id == new_tech_id).first()
                        current_user = db.query(User).filter(User.username == app.storage.user.get('username')).first()

                        update = TicketUpdate(ticket_id=ticket_id, author_id=current_user.id, comment=f"Ticket reasignado de {old_technician.username if old_technician else 'Sin asignar'} a {new_tech_user.username}. Motivo: {reason}")
                        db.add(update)

                        ticket_to_update.technician_id = new_tech_id
                        ticket_to_update.assigned_at = datetime.now(timezone.utc)
                        db.commit()

                        notifier.notify_reassignment(ticket_to_update, old_technician, current_user)
                        notifier.notify_ticket_update(ticket_to_update, update)
                        
                        ui.notify("Ticket reasignado.", color='positive')
                        build_ticket_view() # Refrescar la vista
                    except Exception as e:
                        db.rollback()
                        ui.notify(f"Error al reasignar: {e}", color='negative')
                    finally:
                        db.close()

            def handle_technician_update(new_status, comment):
                db = SessionLocal()
                try:
                    ticket_to_update = db.query(Ticket).options(joinedload(Ticket.technician), joinedload(Ticket.creator)).filter(Ticket.id == ticket_id).first()
                    if not ticket_to_update: return ui.notify("Ticket no encontrado.", color='negative')

                    current_user = db.query(User).filter(User.username == app.storage.user.get('username')).first()
                    if not comment and new_status == ticket_to_update.status: return ui.notify("No hay cambios para guardar.", color='info')

                    updates_to_notify = []
                    if comment:
                        update = TicketUpdate(ticket_id=ticket_id, author_id=current_user.id, comment=comment)
                        db.add(update)
                        updates_to_notify.append(update)

                    if new_status and new_status != ticket_to_update.status:
                        status_comment = f"Estado cambiado de {ticket_to_update.status.value} a {new_status.value}."
                        status_update = TicketUpdate(ticket_id=ticket_id, author_id=current_user.id, comment=status_comment)
                        db.add(status_update)
                        ticket_to_update.status = new_status
                        if new_status == TicketStatus.RESUELTO:
                            ticket_to_update.resolved_at = datetime.now(timezone.utc)
                        updates_to_notify.append(status_update)

                    db.commit()
                    ui.notify("Ticket actualizado.", color='positive')
                    for update in updates_to_notify:
                        db.refresh(update)
                        notifier.notify_ticket_update(ticket_to_update, update)
                    build_ticket_view() # Refrescar la vista
                except Exception as e:
                    db.rollback()
                    ui.notify(f"Error al actualizar: {e}", color='negative')
                finally:
                    db.close()

            def handle_classify_and_assign(problem_type_id, urgency_str, technician_id, location_id):
                if not all([problem_type_id, urgency_str, technician_id, location_id]): return ui.notify("Debe completar todos los campos.", color='negative')

                db = SessionLocal()
                try:
                    ticket_to_update = db.query(Ticket).options(joinedload(Ticket.technician), joinedload(Ticket.creator)).filter(Ticket.id == ticket_id).first()
                    if not ticket_to_update: return ui.notify("Ticket no encontrado.", color='negative')

                    current_user = db.query(User).filter(User.username == app.storage.user.get('username')).first()
                    problem_type = db.query(ProblemType).filter(ProblemType.id == problem_type_id).first()
                    tech_user = db.query(User).filter(User.id == technician_id).first()
                    location = db.query(Location).filter(Location.id == location_id).first()

                    ticket_to_update.problem_type_id = problem_type_id
                    ticket_to_update.urgency = TicketUrgency[urgency_str]
                    ticket_to_update.location_id = location_id

                    class_comment = f"Ticket clasificado con urgencia '{urgency_str}', tipo '{problem_type.name}' y ubicación '{location.description}'."
                    class_update = TicketUpdate(ticket_id=ticket_id, author_id=current_user.id, comment=class_comment)
                    db.add(class_update)

                    ticket_to_update.technician_id = technician_id
                    ticket_to_update.status = TicketStatus.ASIGNADO
                    ticket_to_update.assigned_at = datetime.now(timezone.utc)
                    assign_update = TicketUpdate(ticket_id=ticket_id, author_id=current_user.id, comment=f"Ticket asignado a {tech_user.username}.")
                    db.add(assign_update)

                    db.commit()
                    db.refresh(ticket_to_update)
                    db.refresh(class_update)
                    db.refresh(assign_update)
                    
                    ui.notify("Ticket clasificado y asignado correctamente", color='positive')
                    notifier.notify_ticket_assigned(ticket_to_update, current_user)
                    notifier.notify_ticket_update(ticket_to_update, class_update)
                    build_ticket_view() # Refrescar la vista
                except Exception as e:
                    db.rollback()
                    ui.notify(f"Error al clasificar y asignar: {e}", color='negative')
                finally:
                    db.close()

            # --- Data Loading for the View ---
            db = SessionLocal()
            try:
                ticket = db.query(Ticket).options(
                    joinedload(Ticket.requester),
                    joinedload(Ticket.creator).joinedload(User.location),
                    joinedload(Ticket.technician),
                    joinedload(Ticket.problem_type),
                    joinedload(Ticket.updates).joinedload(TicketUpdate.author),
                    joinedload(Ticket.location)
                ).filter(Ticket.id == ticket_id).first()

                if not ticket:
                    with ui.column().classes('w-full items-center p-8'):
                        ui.label("Ticket no encontrado").classes('text-2xl text-red-500')
                    return

                current_user_role = app.storage.user.get('role')
                is_supervisor = current_user_role in [UserRole.SUPERVISOR.value, UserRole.MONITOR.value, UserRole.ADMINISTRADOR.value]
                is_assigned_technician = ticket.technician and app.storage.user.get('username') == ticket.technician.username
                problem_types_list = db.query(ProblemType).all()
                technicians_list = db.query(User).filter(User.role == UserRole.TECNICO, User.is_active == 1).all()
                locations_list = db.query(Location).all()
            finally:
                db.close()

            # --- UI Construction ---
            with ui.column().classes('w-full p-4 md:p-6 lg:p-8 gap-6'):
                with ui.row().classes('w-full justify-between items-start'):
                    with ui.column().classes('gap-1 flex-grow'):
                        ui.label(f"Ticket #{ticket.id}").classes('text-lg text-gray-500')
                        title_view = ui.label(ticket.title).classes('text-3xl font-bold text-gray-800')
                        title_edit = ui.input(value=ticket.title).classes('w-full text-3xl font-bold').props('dense borderless')
                    
                    with ui.column().classes('items-end'):
                        status_colors = {
                            TicketStatus.NUEVO: 'bg-blue-500', TicketStatus.ASIGNADO: 'bg-yellow-500',
                            TicketStatus.EN_PROCESO: 'bg-orange-500', TicketStatus.RESUELTO: 'bg-green-500',
                            TicketStatus.CERRADO: 'bg-gray-500', TicketStatus.RECHAZADO: 'bg-red-500',
                        }
                        ui.badge(ticket.status.value, color=status_colors.get(ticket.status, 'gray')).classes('text-white text-md px-4 py-2 rounded-full')

                with ui.row().classes('w-full grid grid-cols-1 lg:grid-cols-3 gap-6'):
                    with ui.column().classes('lg:col-span-2 flex flex-col gap-6'):
                        with ui.card().classes('w-full rounded-xl shadow-md p-6'):
                            with ui.row().classes('w-full justify-between items-center mb-4'):
                                ui.label("Descripción del Problema").classes('text-xl font-semibold text-gray-700')
                                if is_supervisor:
                                    edit_button = ui.button('Editar', icon='edit').props('flat color=primary')
                                    with ui.row().classes('gap-2') as edit_actions:
                                        ui.button('Guardar', icon='save', on_click=lambda: handle_details_update(title_edit.value, desc_edit.value)).props('color=positive')
                                        cancel_button = ui.button('Cancelar', icon='cancel').props('flat color=negative')

                            ui.separator()
                            desc_view = ui.markdown(ticket.description or '_Sin descripción._').classes('text-gray-600 mt-4')
                            desc_edit = ui.textarea(value=ticket.description or '').classes('w-full mt-4').props('filled')

                            title_view.visible, title_edit.visible = True, False
                            desc_view.visible, desc_edit.visible = True, False
                            if is_supervisor:
                                edit_actions.visible = False
                                def toggle_edit_mode(editing: bool):
                                    title_view.visible, title_edit.visible = not editing, editing
                                    desc_view.visible, desc_edit.visible = not editing, editing
                                    edit_button.visible, edit_actions.visible = not editing, editing
                                edit_button.on('click', lambda: toggle_edit_mode(True))
                                cancel_button.on('click', lambda: toggle_edit_mode(False))

                        with ui.card().classes('w-full rounded-xl shadow-md p-6') as card_actions:
                            if is_supervisor and ticket.status == TicketStatus.NUEVO:
                                ui.label("Gestión de Asignación").classes('text-xl font-semibold text-gray-700 mb-4')
                                if ticket.problem_type_id is None:
                                    ui.label("Clasificar y Asignar Ticket").classes('text-md text-gray-600 mb-4')
                                    with ui.grid(columns=2).classes('w-full gap-4'):
                                        problem_type_select = ui.select({p.id: p.name for p in problem_types_list}).props("filled label='Tipo de Problema'")
                                        urgency_select = ui.select({u.name: u.value for u in TicketUrgency}).props("filled label='Urgencia'")
                                        tech_select = ui.select({t.id: t.username for t in technicians_list}).props("filled label='Asignar a Técnico'")
                                        
                                        all_locations_dict = {loc.id: loc.description for loc in locations_list}
                                        location_select = ui.select(
                                            all_locations_dict,
                                            label="Ubicación"
                                        ).props('filled use-input').classes('w-full')

                                        def filter_locations(e):
                                            text = e.args[0] if e.args else ''
                                            filtered = {
                                                loc.id: loc.description for loc in locations_list
                                                if not text or text.lower() in loc.description.lower() or text.lower() in loc.name.lower()
                                            }
                                            location_select.options = filtered
                                            location_select.update()
                                        location_select.on('filter', filter_locations)
                                    with ui.row().classes('w-full justify-end gap-2 mt-2'):
                                        ui.button("Guardar y Asignar", on_click=lambda: handle_classify_and_assign(problem_type_select.value, urgency_select.value, tech_select.value, location_select.value), color='primary')
                                        ui.button("Rechazar Ticket", on_click=reject_ticket, color='negative')
                                else:
                                    tech_select = ui.select({t.id: t.username for t in technicians_list}).props("filled label='Seleccionar Técnico'").classes('w-full')
                                    with ui.row().classes('w-full justify-end gap-2 mt-2'):
                                        ui.button("Asignar", on_click=lambda: assign_ticket(tech_select.value), color='primary')
                                        ui.button("Rechazar", on_click=reject_ticket, color='negative')
                            
                            elif is_supervisor and ticket.status in [TicketStatus.ASIGNADO, TicketStatus.EN_PROCESO]:
                                ui.label("Gestión de Asignación").classes('text-xl font-semibold text-gray-700 mb-4')
                                ui.label(f"Actualmente asignado a: {ticket.technician.username}")
                                ui.button("Reasignar Ticket", on_click=reassign_ticket, icon='swap_horiz').props('outline')

                            if is_assigned_technician and ticket.status not in [TicketStatus.RESUELTO, TicketStatus.CERRADO, TicketStatus.RECHAZADO]:
                                ui.label("Actualizar Ticket").classes('text-xl font-semibold text-gray-700 mb-4')
                                possible_statuses = [TicketStatus.EN_PROCESO, TicketStatus.RESUELTO]
                                all_status_options = list(dict.fromkeys([ticket.status] + possible_statuses))
                                status_options = {s: s.value for s in all_status_options}
                                status_select = ui.select(status_options, value=ticket.status).props("filled label='Cambiar Estado'")
                                comment_input = ui.textarea().props("filled label='Añadir comentario o descripción de la solución'").classes('w-full')
                                ui.button("Guardar Actualización", on_click=lambda: handle_technician_update(status_select.value, comment_input.value), color='primary', icon='save')
                            
                            if not card_actions.default_slot.children:
                                card_actions.visible = False

                        with ui.card().classes('w-full rounded-xl shadow-md p-6'):
                            ui.label("Historial de Eventos").classes('text-xl font-semibold text-gray-700 mb-4')
                            with ui.timeline(side='left').classes('w-full'):
                                created_subtitle = to_local_time(ticket.created_at)
                                ui.timeline_entry(f"Ticket creado por {ticket.creator.username}", subtitle=created_subtitle, icon='add_circle', color='grey-6')
                                for update in sorted(ticket.updates, key=lambda u: u.timestamp):
                                    update_subtitle = f"{update.author.username} - {to_local_time(update.timestamp)}"
                                    ui.timeline_entry(update.comment, subtitle=update_subtitle, icon='comment', color='blue-6')

                with ui.column().classes('lg:col-span-1 flex flex-col gap-6'):
                    with ui.card().classes('w-full rounded-xl shadow-md p-6'):
                        ui.label("Atributos").classes('text-xl font-semibold text-gray-700 mb-2')
                        ui.separator()
                        with ui.list().classes('mt-4'):
                            def add_attribute(icon, label, value):
                                with ui.item().classes('w-full p-0'):
                                    with ui.row().classes(
                                        'w-full items-center gap-3 p-2'
                                    ):
                                        ui.icon(icon, color='gray-6').classes('text-lg')
                                        with ui.column().classes('gap-0 flex-grow'):
                                            ui.label(label).classes('text-gray-500 text-xs')
                                            ui.label(value).classes('font-semibold')
                            
                            add_attribute('person', 'Solicitante', ticket.requester.username)
                            add_attribute('engineering', 'Técnico Asignado', ticket.technician.username if ticket.technician else 'Sin asignar')
                            add_attribute('category', 'Tipo de Problema', ticket.problem_type.name if ticket.problem_type else 'Sin clasificar')
                            add_attribute('location_on', 'Ubicación', ticket.location.description if ticket.location else 'No especificada')
                            add_attribute('priority_high', 'Urgencia', ticket.urgency.value if ticket.urgency else 'Sin clasificar')
                            add_attribute('calendar_today', 'Fecha Creación', to_local_time(ticket.created_at))
                            if ticket.resolved_at:
                                add_attribute('task_alt', 'Fecha Resolución', to_local_time(ticket.resolved_at))

    # --- Renderizado Inicial ---
    build_ticket_view()


@ui.page('/search')
def search_tickets_page():
    if not app.storage.user.get('authenticated', False):
        return ui.navigate.to('/')
    create_main_layout()
    search_page()

# --- PÁGINAS DE ADMINISTRACIÓN ---
@ui.page('/admin/users')
def admin_users():
    if not app.storage.user.get('authenticated', False) or app.storage.user.get('role') != 'administrador':
        return ui.navigate.to('/')
    
    from database import SessionLocal, get_password_hash
    from models import User, UserRole

    def get_users_as_dicts():
        db = SessionLocal()
        users = db.query(User).all()
        db.close()
        
        users_list = []
        for user in users:
            users_list.append({
                'id': user.id,
                'username': user.username,
                'full_name': user.full_name,
                'email': user.email,
                'role': user.role.value,
                'is_active': user.is_active,
                'is_active_str': 'Sí' if user.is_active else 'No'
            })
        return users_list

    def save_user(user_data, dialog):
        db = SessionLocal()
        try:
            # Validar si el email ya existe
            existing_user_query = db.query(User).filter(User.email == user_data['email'])
            if user_data.get('id'):
                existing_user_query = existing_user_query.filter(User.id != user_data['id'])
            
            if existing_user_query.first(): # Si ya existe un usuario con ese email
                ui.notify("Esta cuenta de correo ya está registrada.", color='negative')
                db.close()
                return

            if user_data.get('id'): # Modo Edición
                user = db.query(User).filter(User.id == user_data['id']).first()
                if user:
                    user.full_name = user_data['full_name']
                    user.email = user_data['email']
                    user.role = UserRole(user_data['role'])
                    if user_data.get('password'):
                        user.password_hash = get_password_hash(user_data['password'])
                        ui.notify("Contraseña actualizada.", color='info')
            else: # Modo de Creación
                if db.query(User).filter(User.username == user_data['username']).first():
                    ui.notify("Este nombre de usuario ya existe.", color='negative')
                    db.close()
                    return

                hashed_password = get_password_hash(user_data['password'])
                user = User(
                    username=user_data['username'],
                    full_name=user_data['full_name'],
                    email=user_data['email'],
                    password_hash=hashed_password,
                    role=UserRole(user_data['role'])
                )
                db.add(user)
            
            db.commit()
            ui.notify(f"Usuario '{user.username}' guardado correctamente.", color='positive')
            dialog.close()
            table.rows = get_users_as_dicts()
            table.update()

        except Exception as e:
            db.rollback()
            ui.notify(f"Error al guardar usuario: {e}", color='negative')
        finally:
            db.close()

    def open_user_dialog(user_row=None):
        with ui.dialog() as dialog, ui.card().classes('w-full max-w-lg rounded-lg'):
            is_edit = user_row is not None
            ui.label('Editar Usuario' if is_edit else 'Añadir Usuario').classes('text-xl font-semibold p-4 bg-gray-100 w-full text-center')
            
            with ui.column().classes('p-6 gap-4 w-full'):
                if not is_edit:
                    username_input = ui.input("Nombre de usuario").props('filled').classes('w-full')
                
                full_name_input = ui.input("Nombre completo", value=user_row.get('full_name', '') if is_edit else '').props('filled').classes('w-full')
                email_input = ui.input("Email", value=user_row.get('email', '') if is_edit else '').props('filled').classes('w-full')
                role_input = ui.select([role.value for role in UserRole], label="Rol", value=user_row.get('role', UserRole.TECNICO.value) if is_edit else UserRole.TECNICO.value).props('filled').classes('w-full')
                
                password_label = "Contraseña" if not is_edit else "Nueva Contraseña (opcional)"
                password_input = ui.input(password_label, password=True).props('filled').classes('w-full')
                
                if is_edit:
                    confirm_password_input = ui.input("Confirmar Nueva Contraseña", password=True).props('filled').classes('w-full')

            def handle_save():
                if not all([full_name_input.value, email_input.value, role_input.value]):
                    ui.notify("Por favor, complete todos los campos obligatorios.", color='warning')
                    return
                
                user_data = {
                    'id': user_row['id'] if is_edit else None,
                    'full_name': full_name_input.value,
                    'email': email_input.value,
                    'role': role_input.value,
                }

                if not is_edit:
                    if not all([username_input.value, password_input.value]):
                        ui.notify("Para un nuevo usuario, el nombre de usuario y la contraseña son obligatorios.", color='warning')
                        return
                    user_data['username'] = username_input.value
                    user_data['password'] = password_input.value
                else: # Es modo de edición
                    if password_input.value: # Si se ingresó una nueva contraseña
                        if password_input.value != confirm_password_input.value:
                            ui.notify("Las contraseñas no coinciden.", color='negative')
                            return
                        user_data['password'] = password_input.value

                save_user(user_data, dialog)

            with ui.row().classes('w-full justify-end gap-2 p-4 bg-gray-100'):
                ui.button("Guardar", on_click=handle_save, color='primary')
                ui.button("Cancelar", on_click=dialog.close)
        dialog.open()

    def toggle_active_status(user_row):
        db = SessionLocal()
        user = db.query(User).filter(User.id == user_row['id']).first()
        if user:
            user.is_active = 1 - user.is_active
            db.commit()
            ui.notify(f"Usuario {user.username} {'activado' if user.is_active else 'desactivado'}.", color='positive' if user.is_active else 'warning')
        db.close()
        table.rows = get_users_as_dicts()
        table.update()

    create_main_layout()
    with ui.column().classes('w-full p-4 md:p-6 lg:p-8 gap-6'):
        with ui.card().classes('w-full rounded-xl shadow-md p-6'):
            with ui.row().classes('w-full justify-between items-center mb-6'):
                ui.label("Gestión de Usuarios").classes('text-2xl font-bold text-gray-800')
                ui.button("Añadir Usuario", on_click=open_user_dialog, icon='add').props('color=primary')

            columns = [
                {'name': 'id', 'label': 'ID', 'field': 'id', 'sortable': True, 'classes': 'font-bold'},
                {'name': 'username', 'label': 'Usuario', 'field': 'username', 'sortable': True, 'align': 'left'},
                {'name': 'full_name', 'label': 'Nombre Completo', 'field': 'full_name', 'align': 'left'},
                {'name': 'email', 'label': 'Email', 'field': 'email', 'align': 'left'},
                {'name': 'role', 'label': 'Rol', 'field': 'role', 'sortable': True},
                {'name': 'is_active_str', 'label': 'Activo', 'field': 'is_active_str'},
                {'name': 'actions', 'label': 'Acciones', 'align': 'right'},
            ]

            table = ui.table(columns=columns, rows=get_users_as_dicts(), row_key='id').classes('w-full')
            table.add_slot('body-cell-actions', '''
                <q-td :props="props">
                    <div class="flex items-center justify-end gap-2">
                        <q-btn flat round color="primary" icon="edit" @click="() => $parent.$emit('edit', props.row)"></q-btn>
                        <q-btn flat round :color="props.row.is_active ? 'negative' : 'positive'" :icon="props.row.is_active ? 'toggle_off' : 'toggle_on'" @click="() => $parent.$emit('toggle', props.row)"></q-btn>
                    </div>
                </q-td>
            ''')

            table.on('edit', lambda e: open_user_dialog(e.args))
            table.on('toggle', lambda e: toggle_active_status(e.args))

@ui.page('/admin/locations')
def admin_locations():
    if not app.storage.user.get('authenticated', False) or app.storage.user.get('role') != 'administrador':
        return ui.navigate.to('/')

    from database import SessionLocal
    from models import Location

    def get_locations_as_dicts():
        db = SessionLocal()
        locations = db.query(Location).all()
        db.close()
        return [{'id': loc.id, 'name': loc.name, 'description': loc.description} for loc in locations]

    def save_location(data, dialog):
        db = SessionLocal()
        try:
            if not data['name']:
                ui.notify("El nombre es obligatorio.", color='negative')
                return
            if data.get('id'):
                location = db.query(Location).filter(Location.id == data['id']).first()
                if location:
                    location.name = data['name']
                    location.description = data['description']
            else:
                location = Location(name=data['name'], description=data['description'])
                db.add(location)
            db.commit()
            ui.notify(f"Ubicación '{location.name}' guardada.", color='positive')
            dialog.close()
            table.rows = get_locations_as_dicts()
            table.update()
        except Exception as e:
            db.rollback()
            ui.notify(f"Error al guardar: {e}", color='negative')
        finally:
            db.close()

    async def delete_location(location_row):
        with ui.dialog() as confirm_dialog, ui.card().classes('rounded-lg'):
            ui.label(f"¿Estás seguro de que quieres borrar la ubicación '{location_row['name']}'?").classes('p-4 text-lg')
            with ui.row().classes('w-full justify-end gap-2 p-4 bg-gray-100'):
                ui.button("Sí, borrar", on_click=lambda: confirm_dialog.submit(True), color='negative')
                ui.button("No, cancelar", on_click=lambda: confirm_dialog.submit(False))
        
        if await confirm_dialog:
            db = SessionLocal()
            try:
                location = db.query(Location).filter(Location.id == location_row['id']).first()
                if location:
                    db.delete(location)
                    db.commit()
                    ui.notify(f"Ubicación '{location.name}' borrada.", color='positive')
                else:
                    ui.notify("La ubicación ya no existe.", color='warning')
                table.rows = get_locations_as_dicts()
                table.update()
            except Exception as e:
                db.rollback()
                ui.notify(f"Error al borrar: {e}", color='negative')
            finally:
                db.close()

    def open_dialog(location_row=None):
        with ui.dialog() as dialog, ui.card().classes('w-full max-w-lg rounded-lg'):
            ui.label('Editar Ubicación' if location_row else 'Añadir Ubicación').classes('text-xl font-semibold p-4 bg-gray-100 w-full text-center')
            with ui.column().classes('p-6 gap-4 w-full'):
                name_input = ui.input("Nombre", value=location_row['name'] if location_row else '').props('filled').classes('w-full')
                desc_input = ui.input("Descripción", value=location_row['description'] if location_row else '').props('filled').classes('w-full')
            
            def handle_save():
                data = {'id': location_row['id'] if location_row else None, 'name': name_input.value, 'description': desc_input.value}
                save_location(data, dialog)

            with ui.row().classes('w-full justify-end gap-2 p-4 bg-gray-100'):
                ui.button("Guardar", on_click=handle_save, color='primary')
                ui.button("Cancelar", on_click=dialog.close)
        dialog.open()

    create_main_layout()
    with ui.column().classes('w-full p-4 md:p-6 lg:p-8 gap-6'):
        with ui.card().classes('w-full rounded-xl shadow-md p-6'):
            with ui.row().classes('w-full justify-between items-center mb-6'):
                ui.label("Gestión de Ubicaciones").classes('text-2xl font-bold text-gray-800')
                ui.button("Añadir Ubicación", on_click=open_dialog, icon='add').props('color=primary')

            columns = [
                {'name': 'name', 'label': 'Nombre', 'field': 'name', 'sortable': True, 'align': 'left'},
                {'name': 'description', 'label': 'Descripción', 'field': 'description', 'align': 'left'},
                {'name': 'actions', 'label': 'Acciones', 'align': 'right'},
            ]
            table = ui.table(columns=columns, rows=get_locations_as_dicts(), row_key='id').classes('w-full')
            table.add_slot('body-cell-actions', '''
                <q-td :props="props">
                    <div class="flex items-center justify-end gap-2">
                        <q-btn flat round color="primary" icon="edit" @click="() => $parent.$emit('edit', props.row)"></q-btn>
                        <q-btn flat round color="negative" icon="delete" @click="() => $parent.$emit('delete', props.row)"></q-btn>
                    </div>
                </q-td>
            ''')
            table.on('edit', lambda e: open_dialog(e.args))
            table.on('delete', lambda e: delete_location(e.args))

@ui.page('/admin/itil_categories')
def admin_itil_categories():
    if not app.storage.user.get('authenticated', False) or app.storage.user.get('role') != 'administrador':
        return ui.navigate.to('/')

    from database import SessionLocal
    from models import ITILCategory, ITILSubCategory, ProblemType

    def load_data():
        db = SessionLocal()
        categories = db.query(ITILCategory).options(
            joinedload(ITILCategory.subcategories).joinedload(ITILSubCategory.problem_types)
        ).all()
        db.close()
        return categories

    def open_category_dialog(category=None):
        with ui.dialog() as dialog, ui.card().classes('w-full max-w-lg rounded-lg'):
            is_edit = category is not None
            ui.label('Editar Categoría' if is_edit else 'Añadir Categoría').classes('text-xl font-semibold p-4 bg-gray-100 w-full text-center')
            name_input = ui.input("Nombre de la Categoría", value=category.name if is_edit else '').props('filled').classes('w-full')
            
            def save_category():
                db = SessionLocal()
                try:
                    if is_edit:
                        category.name = name_input.value
                        db.merge(category)
                    else:
                        new_category = ITILCategory(name=name_input.value)
                        db.add(new_category)
                    db.commit()
                    ui.notify("Categoría guardada", color='positive')
                    dialog.close()
                    # Reload the entire page to reflect changes
                    ui.navigate.reload()
                except Exception as e:
                    db.rollback()
                    ui.notify(f"Error al guardar categoría: {e}", color='negative')
                finally:
                    db.close()

            with ui.row().classes('w-full justify-end gap-2 p-4 bg-gray-100'):
                ui.button("Guardar", on_click=save_category, color='primary')
                ui.button("Cancelar", on_click=dialog.close)
        dialog.open()

    def open_subcategory_dialog(category, subcategory=None):
        with ui.dialog() as dialog, ui.card().classes('w-full max-w-lg rounded-lg'):
            is_edit = subcategory is not None
            ui.label(f'Editar Subcategoría en {category.name}' if is_edit else f'Añadir Subcategoría en {category.name}').classes('text-xl font-semibold p-4 bg-gray-100 w-full text-center')
            name_input = ui.input("Nombre de la Subcategoría", value=subcategory.name if is_edit else '').props('filled').classes('w-full')
            
            def save_subcategory():
                db = SessionLocal()
                try:
                    if is_edit:
                        subcategory.name = name_input.value
                        db.merge(subcategory)
                    else:
                        new_subcategory = ITILSubCategory(name=name_input.value, category_id=category.id)
                        db.add(new_subcategory)
                    db.commit()
                    ui.notify("Subcategoría guardada", color='positive')
                    dialog.close()
                    ui.navigate.reload()
                except Exception as e:
                    db.rollback()
                    ui.notify(f"Error al guardar subcategoría: {e}", color='negative')
                finally:
                    db.close()

            with ui.row().classes('w-full justify-end gap-2 p-4 bg-gray-100'):
                ui.button("Guardar", on_click=save_subcategory, color='primary')
                ui.button("Cancelar", on_click=dialog.close)
        dialog.open()

    def open_problem_type_dialog(subcategory, problem_type=None):
        with ui.dialog() as dialog, ui.card().classes('w-full max-w-lg rounded-lg'):
            is_edit = problem_type is not None
            ui.label(f'Editar Tipo de Problema en {subcategory.name}' if is_edit else f'Añadir Tipo de Problema en {subcategory.name}').classes('text-xl font-semibold p-4 bg-gray-100 w-full text-center')
            name_input = ui.input("Nombre del Tipo de Problema", value=problem_type.name if is_edit else '').props('filled').classes('w-full')
            description_input = ui.textarea("Descripción", value=problem_type.description if is_edit else '').props('filled').classes('w-full')
            
            def save_problem_type():
                db = SessionLocal()
                try:
                    if is_edit:
                        problem_type.name = name_input.value
                        problem_type.description = description_input.value
                        db.merge(problem_type)
                    else:
                        new_problem_type = ProblemType(name=name_input.value, description=description_input.value, subcategory_id=subcategory.id)
                        db.add(new_problem_type)
                    db.commit()
                    ui.notify("Tipo de problema guardado", color='positive')
                    dialog.close()
                    ui.navigate.reload()
                except Exception as e:
                    db.rollback()
                    ui.notify(f"Error al guardar tipo de problema: {e}", color='negative')
                finally:
                    db.close()

            with ui.row().classes('w-full justify-end gap-2 p-4 bg-gray-100'):
                ui.button("Guardar", on_click=save_problem_type, color='primary')
                ui.button("Cancelar", on_click=dialog.close)
        dialog.open()

    async def delete_category(category):
        if await ui.run_dialog(f'¿Estás seguro de que quieres eliminar la categoría "{category.name}" y todas sus subcategorías y tipos de problema asociados?', title='Confirmar Eliminación'):
            db = SessionLocal()
            try:
                db.delete(category)
                db.commit()
                ui.notify(f'Categoría "{category.name}" eliminada.', color='positive')
                ui.navigate.reload()
            except Exception as e:
                db.rollback()
                ui.notify(f'Error al eliminar categoría: {e}', color='negative')
            finally:
                db.close()

    async def delete_subcategory(subcategory):
        if await ui.run_dialog(f'¿Estás seguro de que quieres eliminar la subcategoría "{subcategory.name}" y todos sus tipos de problema asociados?', title='Confirmar Eliminación'):
            db = SessionLocal()
            try:
                db.delete(subcategory)
                db.commit()
                ui.notify(f'Subcategoría "{subcategory.name}" eliminada.', color='positive')
                ui.navigate.reload()
            except Exception as e:
                db.rollback()
                ui.notify(f'Error al eliminar subcategoría: {e}', color='negative')
            finally:
                db.close()

    async def delete_problem_type(problem_type):
        if await ui.run_dialog(f'¿Estás seguro de que quieres eliminar el tipo de problema "{problem_type.name}"?', title='Confirmar Eliminación'):
            db = SessionLocal()
            try:
                db.delete(problem_type)
                db.commit()
                ui.notify(f'Tipo de problema "{problem_type.name}" eliminado.', color='positive')
                ui.navigate.reload()
            except Exception as e:
                db.rollback()
                ui.notify(f'Error al eliminar tipo de problema: {e}', color='negative')
            finally:
                db.close()

    create_main_layout()
    with ui.column().classes('w-full p-4 md:p-6 lg:p-8 gap-6'):
        with ui.card().classes('w-full rounded-xl shadow-md p-6'):
            with ui.row().classes('w-full justify-between items-center mb-6'):
                ui.label("Gestión de Categorías ITIL").classes('text-2xl font-bold text-gray-800')
                ui.button("Añadir Categoría", on_click=lambda: open_category_dialog(), icon='add').props('color=primary')

            for category in load_data():
                with ui.expansion(category.name, icon='category').classes('w-full'):
                    with ui.row().classes('w-full justify-end'):
                        ui.button("Añadir Subcategoría", on_click=lambda cat=category: open_subcategory_dialog(cat), icon='add').props('flat dense')
                        ui.button("Editar Categoría", on_click=lambda cat=category: open_category_dialog(cat), icon='edit').props('flat dense')
                        ui.button("Eliminar Categoría", on_click=lambda cat=category: delete_category(cat), icon='delete').props('flat dense color=negative')
                    with ui.column().classes('w-full p-4'):
                        for subcategory in category.subcategories:
                            with ui.expansion(subcategory.name, icon='subdirectory_arrow_right').classes('w-full'):
                                with ui.row().classes('w-full justify-end'):
                                    ui.button("Añadir Tipo de Problema", on_click=lambda sub=subcategory: open_problem_type_dialog(sub), icon='add').props('flat dense')
                                    ui.button("Editar Subcategoría", on_click=lambda sub=subcategory: open_subcategory_dialog(category, sub), icon='edit').props('flat dense')
                                    ui.button("Eliminar Subcategoría", on_click=lambda sub=subcategory: delete_subcategory(sub), icon='delete').props('flat dense color=negative')
                                with ui.column().classes('w-full p-4'):
                                    for problem_type in subcategory.problem_types:
                                        with ui.row().classes('w-full justify-between items-center'):
                                            ui.label(problem_type.name)
                                            with ui.row():
                                                ui.button(icon='edit', on_click=lambda pt=problem_type: open_problem_type_dialog(subcategory, pt)).props('flat dense')
                                                ui.button(icon='delete', on_click=lambda pt=problem_type: delete_problem_type(pt)).props('flat dense color=negative')

@ui.page('/admin/slas')
def admin_slas():
    if not app.storage.user.get('authenticated', False) or app.storage.user.get('role') != 'administrador':
        return ui.navigate.to('/')

    from database import SessionLocal
    from models import SLA, TicketUrgency

    def load_data():
        db = SessionLocal()
        slas = db.query(SLA).order_by(SLA.id).all()
        db.close()
        return [{'id': sla.id, 'urgency': sla.urgency.value, 'assignment_time_hours': sla.assignment_time_hours, 'resolution_time_hours': sla.resolution_time_hours} for sla in slas]

    def save_sla(data, dialog):
        db = SessionLocal()
        try:
            sla = db.query(SLA).filter(SLA.id == data['id']).first()
            if sla:
                sla.assignment_time_hours = data['assignment_time_hours']
                sla.resolution_time_hours = data['resolution_time_hours']
                db.commit()
                ui.notify(f"SLA para urgencia '{sla.urgency.value}' actualizado.", color='positive')
            else:
                ui.notify("SLA no encontrado.", color='warning')
            dialog.close()
            table.rows = load_data()
            table.update()
        except Exception as e:
            db.rollback()
            ui.notify(f"Error al guardar: {e}", color='negative')
        finally:
            db.close()

    def open_edit_dialog(sla_row):
        with ui.dialog() as dialog, ui.card().classes('w-full max-w-lg rounded-lg'):
            ui.label(f"Editando SLA para Urgencia: {sla_row['urgency'].upper()}").classes('text-xl font-semibold p-4 bg-gray-100 w-full text-center')
            with ui.column().classes('p-6 gap-4 w-full'):
                assign_input = ui.number("Tiempo de Asignación (horas)", value=sla_row['assignment_time_hours'], min=1).props('filled').classes('w-full')
                resolve_input = ui.number("Tiempo de Resolución (horas)", value=sla_row['resolution_time_hours'], min=1).props('filled').classes('w-full')
            
            def handle_save():
                data = {'id': sla_row['id'], 'assignment_time_hours': assign_input.value, 'resolution_time_hours': resolve_input.value}
                save_sla(data, dialog)

            with ui.row().classes('w-full justify-end gap-2 p-4 bg-gray-100'):
                ui.button("Guardar", on_click=handle_save, color='primary')
                ui.button("Cancelar", on_click=dialog.close)
        dialog.open()

    create_main_layout()
    with ui.column().classes('w-full p-4 md:p-6 lg:p-8 gap-6'):
        with ui.card().classes('w-full rounded-xl shadow-md p-6'):
            with ui.row().classes('w-full justify-between items-center mb-6'):
                ui.label("Gestión de SLAs").classes('text-2xl font-bold text-gray-800')

            columns = [
                {'name': 'urgency', 'label': 'Nivel de Urgencia', 'field': 'urgency', 'align': 'left', 'classes': 'font-bold'},
                {'name': 'assignment_time_hours', 'label': 'Tiempo de Asignación (horas)', 'field': 'assignment_time_hours', 'align': 'center'},
                {'name': 'resolution_time_hours', 'label': 'Tiempo de Resolución (horas)', 'field': 'resolution_time_hours', 'align': 'center'},
                {'name': 'actions', 'label': 'Acciones', 'align': 'right'},
            ]
            table = ui.table(columns=columns, rows=load_data(), row_key='id').classes('w-full')
            table.add_slot('body-cell-actions', '''
                <q-td :props="props">
                    <div class="flex items-center justify-end gap-2">
                        <q-btn flat round color="primary" icon="edit" @click="() => $parent.$emit('edit', props.row)"></q-btn>
                    </div>
                </q-td>
            ''')
            table.on('edit', lambda e: open_edit_dialog(e.args))






# --- LÓGICA DE LOGIN ---
def show_login():
    ui.query('body').classes('bg-gray-100')
    with ui.card().classes('absolute-center w-96 p-8 rounded-lg shadow-xl'):
        with ui.column().classes('w-full items-center gap-4'):
            ui.label('HelpdeskOI').classes('text-3xl font-bold text-gray-700')
            ui.label('Iniciar Sesión').classes('text-xl text-gray-500 mb-4')
            
            username = ui.input('Usuario').props('filled outlined').classes('w-full')
            password = ui.input('Contraseña', password=True).props('filled outlined').classes('w-full')
            
            ui.button('Iniciar Sesión', on_click=lambda: handle_login(username, password))                 .classes('w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 rounded-md mt-4')

def handle_login(username_input, password_input):
    user = authenticate_user(username_input.value, password_input.value)
    if user:
        app.storage.user.update({'id': user.id, 'username': user.username, 'authenticated': True, 'role': user.role.value})
        ui.notify(f"Inicio de sesión exitoso como {user.username}", color='positive')
        ui.navigate.to('/dashboard')
    else:
        ui.notify('Usuario o contraseña incorrectos', color='negative')

# Inicializa la base de datos al arrancar la aplicación
init_db()

_background_tasks = set()

@app.on_startup
async def start_background_tasks():
    """Inicia las tareas de fondo para la revisión de correos y SLAs."""
    async def run_periodically(wait_time, task_function):
        while True:
            try:
                await task_function()
            except Exception as e:
                print(f"Error en tarea de fondo '{task_function.__name__}': {e}")
            await asyncio.sleep(wait_time)

    # Tarea para el lector de correo
    db_session = SessionLocal()
    mail_settings = db_session.query(MailSettings).first()
    if mail_settings and mail_settings.is_active:
        interval = (mail_settings.check_interval_minutes or 5) * 60
        task = asyncio.create_task(run_periodically(interval, check_new_emails))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
        print(f"Lector de correo activado. Revisando cada {interval / 60} minuto(s).")
    else:
        print("Lector de correo desactivado.")
    db_session.close()

    # Tarea para el verificador de SLA
    sla_interval = 600  # 10 minutos
    sla_task = asyncio.create_task(run_periodically(sla_interval, check_sla_warnings))
    _background_tasks.add(sla_task)
    sla_task.add_done_callback(_background_tasks.discard)
    print(f"Verificador de SLA activado. Revisando cada {sla_interval / 60} minutos.")

@app.on_shutdown
def stop_background_tasks():
    """Detiene todas las tareas de fondo al cerrar la aplicación."""
    print("Deteniendo tareas de fondo...")
    for task in _background_tasks:
        task.cancel()
    print("Tareas de fondo detenidas.")

# En una aplicación real, este secreto debe ser largo, aleatorio y cargado de forma segura (p. ej., una variable de entorno)
STORAGE_SECRET = os.environ.get("STORAGE_SECRET")
if not STORAGE_SECRET:
    raise ValueError("La clave secreta de almacenamiento (STORAGE_SECRET) no está configurada en las variables de entorno.")

ui.run(title="HelpdeskOI", favicon='🔧', storage_secret=STORAGE_SECRET, tailwind=True)
