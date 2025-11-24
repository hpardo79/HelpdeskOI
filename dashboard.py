from nicegui import app, ui
from sqlalchemy import func, case
from sqlalchemy.orm import joinedload
from datetime import datetime, timezone

import pytz
from database import SessionLocal
from models import Ticket, User, UserRole, TicketStatus, TicketUrgency, ProblemType, TicketUpdate, Location
from main_layout import create_main_layout
from datetime_utils import to_local_time
import notification_manager as notifier
from ticket_utils import load_tickets

@ui.page('/dashboard')
def dashboard_page():
    if not app.storage.user.get('authenticated', False):
        return ui.navigate.to('/')

    def get_available_years():
        db = SessionLocal()
        try:
            years_query = db.query(func.extract('year', Ticket.created_at)).distinct().order_by(func.extract('year', Ticket.created_at).desc()).all()
            return [year[0] for year in years_query if year[0] is not None]
        finally:
            db.close()

    def get_supervisor_chart_data(year=None, month=None):
        db = SessionLocal()
        try:
            ticket_query = db.query(Ticket)
            if year:
                ticket_query = ticket_query.filter(func.extract('year', Ticket.created_at) == year)
            if month:
                ticket_query = ticket_query.filter(func.extract('month', Ticket.created_at) == month)

            status_data = ticket_query.with_entities(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status).all()
            
            # Consulta para obtener el desglose de tickets por técnico y urgencia
            tech_query = db.query(
                User.username,
                func.count(Ticket.id).label('total'),
                func.sum(case((Ticket.urgency == TicketUrgency.ALTA, 1), else_=0)).label('alta'),
                func.sum(case((Ticket.urgency == TicketUrgency.MEDIA, 1), else_=0)).label('media'),
                func.sum(case((Ticket.urgency == TicketUrgency.BAJA, 1), else_=0)).label('baja')
            ).join(User, Ticket.technician_id == User.id).filter(Ticket.technician_id.isnot(None))

            if year:
                tech_query = tech_query.filter(func.extract('year', Ticket.created_at) == year)
            if month:
                tech_query = tech_query.filter(func.extract('month', Ticket.created_at) == month)
            
            tech_data = tech_query.group_by(User.username).all()

            return status_data, tech_data
        finally:
            db.close()

    def get_technician_stats(user_id, year=None, month=None):
        db = SessionLocal()
        try:
            open_statuses = [TicketStatus.ASIGNADO, TicketStatus.EN_PROCESO]
            
            open_query = db.query(Ticket).filter(Ticket.technician_id == user_id, Ticket.status.in_(open_statuses))
            if year:
                open_query = open_query.filter(func.extract('year', Ticket.created_at) == year)
            if month:
                open_query = open_query.filter(func.extract('month', Ticket.created_at) == month)
            open_count = open_query.count()

            resolved_query = db.query(Ticket).filter(Ticket.technician_id == user_id, Ticket.status == TicketStatus.RESUELTO)
            if year:
                resolved_query = resolved_query.filter(func.extract('year', Ticket.created_at) == year)
            if month:
                resolved_query = resolved_query.filter(func.extract('month', Ticket.created_at) == month)
            resolved_count = resolved_query.count()

            return open_count, resolved_count
        finally:
            db.close()

    # --- Interfaz de la página ---
    create_main_layout()
    with ui.column().classes('w-full p-4 md:p-6 lg:p-8 gap-6'):
        with ui.row().classes('w-full justify-between items-center'):
            ui.label(f"Bienvenido al Dashboard, {app.storage.user.get('username')}").classes('text-2xl font-semibold text-gray-700')
            with ui.column().classes('items-end gap-0'):
                local_clock = ui.label().classes('text-2xl font-bold text-gray-600')
                ui.label('Hora Local (Panamá)').classes('text-xs text-gray-500')

        def update_clocks():
            utc_now = datetime.now(timezone.utc)
            panama_tz = pytz.timezone('America/Panama')
            panama_now = utc_now.astimezone(panama_tz)
            local_clock.set_text(panama_now.strftime('%H:%M:%S'))
        ui.timer(1.0, update_clocks)

        current_role = app.storage.user.get('role')
        
        # --- FILTROS ---
        if current_role in [UserRole.SUPERVISOR.value, UserRole.MONITOR.value, UserRole.ADMINISTRADOR.value, UserRole.TECNICO.value]:
            with ui.card().classes('w-full rounded-xl shadow-md p-4 mb-6'):
                with ui.row().classes('w-full items-center gap-4'):
                    ui.label("Filtros:").classes('text-lg font-semibold')
                    
                    current_year = datetime.now().year
                    available_years = get_available_years()
                    if not available_years:
                        available_years.append(current_year)

                    year_selector = ui.select(available_years, label="Año", value=current_year).props('filled dense bg-white')
                    
                    months = {
                        0: 'Todos los meses', 1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
                        5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto', 9: 'Septiembre',
                        10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
                    }
                    month_selector = ui.select(months, label="Mes", value=datetime.now().month).props('filled dense bg-white')

        @ui.refreshable
        def charts_section():
            year = year_selector.value if 'year_selector' in locals() else None
            month = month_selector.value if 'month_selector' in locals() and month_selector.value != 0 else None
            
            with ui.row().classes('w-full grid grid-cols-1 md:grid-cols-2 gap-6'):
                if current_role in [UserRole.SUPERVISOR.value, UserRole.MONITOR.value, UserRole.ADMINISTRADOR.value]:
                    status_counts, tech_counts = get_supervisor_chart_data(year=year, month=month)
                    
                    with ui.card().classes('w-full rounded-xl shadow-md p-4'):
                        ui.label("Tickets por Estado").classes('text-lg font-semibold text-gray-600 text-center')
                        
                        # Definir mapa de colores para los estados de los tickets
                        status_color_map = {
                            TicketStatus.NUEVO: '#F87171',      # Rojo suave
                            TicketStatus.ASIGNADO: '#FACC15',   # Amarillo
                            TicketStatus.EN_PROCESO: '#FB923C', # Naranja
                            TicketStatus.RESUELTO: '#4ADE80',   # Verde
                            TicketStatus.CERRADO: '#9CA3AF',    # Gris
                            TicketStatus.RECHAZADO: '#60A5FA'   # Azul
                        }

                        if status_counts:
                            ui.echart({
                                'tooltip': {'trigger': 'item'},
                                'legend': {'orient': 'vertical', 'left': 'left'},
                                'series': [{'name': 'Tickets', 'type': 'pie', 'radius': '70%',
                                            'label': {'show': True, 'formatter': '{b}\n{c}', 'position': 'outside'}, 'labelLine': {'show': True},
                                            'data': [{'value': count, 'name': status.value, 'itemStyle': {'color': status_color_map.get(status, '#cccccc')}} for status, count in status_counts if status],
                                            'emphasis': {'itemStyle': {'shadowBlur': 10, 'shadowOffsetX': 0, 'shadowColor': 'rgba(0, 0, 0, 0.5)'}}}]
                            })
                        else:
                            ui.label("No hay datos para este filtro").classes('text-center text-gray-500 p-8')

                    with ui.card().classes('w-full rounded-xl shadow-md p-4'):
                        ui.label("Tickets Asignados por Técnico").classes('text-lg font-semibold text-gray-600 text-center mb-4')
                        if tech_counts:
                            # Ordenar técnicos por cantidad de tickets de forma descendente
                            sorted_techs = sorted(tech_counts, key=lambda item: item.total, reverse=True)
                            with ui.grid().classes('grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 w-full'):
                                for tech in sorted_techs:
                                    with ui.card().classes('p-3 w-full flex flex-col items-center'):
                                        ui.label(tech.username).classes('font-semibold text-gray-700 text-center')
                                        ui.label(tech.total).classes('text-3xl font-bold text-blue-600')
                                        with ui.row().classes('w-full justify-around mt-2 text-xs'):
                                            with ui.column().classes('items-center'):
                                                ui.label('Alta').classes('text-red-500 font-medium')
                                                ui.label(tech.alta).classes('text-red-500 font-bold')
                                            with ui.column().classes('items-center'):
                                                ui.label('Media').classes('text-orange-500 font-medium')
                                                ui.label(tech.media).classes('text-orange-500 font-bold')
                                            with ui.column().classes('items-center'):
                                                ui.label('Baja').classes('text-yellow-500 font-medium')
                                                ui.label(tech.baja).classes('text-yellow-500 font-bold')
                        else:
                            ui.label("No hay datos para este filtro").classes('text-center text-gray-500 p-8 w-full col-span-full')
                
                elif current_role == UserRole.TECNICO.value:
                    db = SessionLocal()
                    user = db.query(User).filter(User.username == app.storage.user.get('username')).first()
                    db.close()
                    open_tickets, resolved_tickets = get_technician_stats(user.id, year=year, month=month)
                    
                    with ui.card().classes('w-full rounded-xl shadow-md p-6 flex flex-col items-center justify-center text-center'):
                        ui.label("Mis Tickets Abiertos").classes('text-lg font-semibold text-gray-500')
                        ui.label(open_tickets).classes('text-5xl font-bold text-blue-600 mt-2')
                    with ui.card().classes('w-full rounded-xl shadow-md p-6 flex flex-col items-center justify-center text-center'):
                        ui.label("Mis Tickets Resueltos").classes('text-lg font-semibold text-gray-500')
                        ui.label(resolved_tickets).classes('text-5xl font-bold text-green-600 mt-2')
                
                elif current_role == UserRole.AUTOSERVICIO.value:
                    with ui.card().classes('w-full rounded-xl shadow-md p-6'):
                        ui.label("Bienvenido").classes('text-lg font-semibold text-gray-600')
                        ui.label("Utilice la tabla de abajo para ver el estado de sus tickets.").classes('text-center text-gray-500 p-4')

        if 'year_selector' in locals():
            year_selector.on('update:model-value', charts_section.refresh)
            month_selector.on('update:model-value', charts_section.refresh)
        
        charts_section()

        with ui.card().classes('w-full rounded-xl shadow-md p-4'):
            with ui.row().classes('w-full justify-between items-center mb-4'):
                ui.label("Tickets Recientes").classes('text-xl font-bold text-gray-800')
                if current_role in [UserRole.SUPERVISOR.value, UserRole.ADMINISTRADOR.value, UserRole.MONITOR.value]:
                    def open_new_ticket_dialog():
                        db = SessionLocal()
                        users = db.query(User).all()
                        technicians = db.query(User).filter(User.role == UserRole.TECNICO, User.is_active == 1).all()
                        all_problem_types = db.query(ProblemType).all()
                        locations = db.query(Location).all()
                        db.close()
                        
                        with ui.dialog() as dialog, ui.card().style('width: 700px; max-width: 90vw;').classes('rounded-lg'):
                            ui.label("Crear Nuevo Ticket").classes('text-xl p-4 font-semibold')
                            with ui.column().classes('w-full p-4 gap-4'):
                                title_input = ui.input("Título").props('filled').classes('w-full')
                                desc_input = ui.textarea("Descripción").props('filled').classes('w-full')

                                with ui.row().classes('w-full gap-4'):
                                    # Por defecto, se selecciona el usuario actual. Si no está disponible, se usa el primero de la lista.
                                    default_requester_id = app.storage.user.get('id')

                                    requester_select = ui.select({u.id: u.username for u in users}, label="Solicitante (Cliente)", value=default_requester_id).props('filled').classes('w-full')
                                    urgency_select = ui.select({u.name: u.value for u in TicketUrgency}, label="Urgencia").props('filled').classes('w-full')
                                
                                with ui.row().classes('w-full gap-4'):
                                    all_locations_dict = {loc.id: loc.description for loc in locations}
                                    location_select = ui.select(
                                        all_locations_dict,
                                        label="Ubicación (Opcional)"
                                    ).props('filled use-input').classes('w-full')

                                    def filter_locations(e):
                                        args = e.args
                                        if not args:
                                            location_select.options = all_locations_dict
                                            location_select.update()
                                            return
                                        text = args[0]
                                        filtered_options = {
                                            loc.id: loc.description for loc in locations
                                            if text.lower() in loc.description.lower() or text.lower() in loc.name.lower()
                                        }
                                        location_select.options = filtered_options
                                        location_select.update()
                                    location_select.on('filter', filter_locations)

                                all_problem_types_dict = {p.id: p.name for p in all_problem_types}
                                problem_type_select = ui.select(
                                    all_problem_types_dict,
                                    label="Tipo de Problema"
                                ).props('filled use-input').classes('w-full')

                                def filter_problem_types(e):
                                    args = e.args
                                    if not args:
                                        problem_type_select.options = all_problem_types_dict
                                        problem_type_select.update()
                                        return
                                    text = args[0]
                                    filtered_options = {
                                        p.id: p.name for p in all_problem_types
                                        if text.lower() in p.name.lower()
                                    }
                                    problem_type_select.options = filtered_options
                                    problem_type_select.update()
                                problem_type_select.on('filter', filter_problem_types)

                                with ui.row().classes('w-full gap-4'):
                                    tech_select_options = {t.id: t.username for t in technicians}
                                    tech_select_options[None] = "Sin asignar"
                                    technician_select = ui.select(tech_select_options, label="Asignar a Técnico (Opcional)", value=None).props('filled').classes('w-full')

                            def handle_save():
                                if not all([title_input.value, requester_select.value, problem_type_select.value, urgency_select.value]):
                                    ui.notify("Por favor, complete todos los campos obligatorios.", color='warning')
                                    return
                                data = {
                                    'title': title_input.value,
                                    'description': desc_input.value,
                                    'requester_id': requester_select.value,
                                    'creator_id': app.storage.user.get('id'), # El creador es el usuario logueado
                                    'problem_type_id': problem_type_select.value,
                                    'location_id': location_select.value,
                                    'created_at': datetime.now(timezone.utc),
                                    'urgency': TicketUrgency[urgency_select.value],
                                }
                                if technician_select.value:
                                    data['technician_id'] = technician_select.value
                                    data['status'] = TicketStatus.ASIGNADO
                                    data['assigned_at'] = datetime.now(timezone.utc)
                                else:
                                    data['status'] = TicketStatus.NUEVO
                                db_session = SessionLocal()
                                try:
                                    new_ticket = Ticket(**data)
                                    db_session.add(new_ticket)
                                    db_session.flush()
                                    new_ticket = db_session.query(Ticket).options(joinedload(Ticket.requester), joinedload(Ticket.creator), joinedload(Ticket.technician)).filter(Ticket.id == new_ticket.id).first()
                                    if new_ticket.technician_id:
                                        update_comment = f"Ticket asignado a {new_ticket.technician.username} durante la creación."
                                        update = TicketUpdate(ticket_id=new_ticket.id, author_id=app.storage.user.get('id'), comment=update_comment)
                                        db_session.add(update)
                                    db_session.commit()
                                    ui.notify("Ticket creado exitosamente.", color='positive')
                                    
                                    # Refrescar el objeto para cargar todas las relaciones necesarias para la notificación
                                    db_session.refresh(new_ticket)
                                    
                                    try:
                                        # El "asignador" es el usuario actual que realiza la acción
                                        assigner = db_session.query(User).filter(User.id == app.storage.user.get('id')).first()
                                        
                                        # Notificar al creador sobre el nuevo ticket
                                        # Se notifica al solicitante (requester), no necesariamente al creador (supervisor/monitor)
                                        if new_ticket.requester:
                                            notifier.notify_new_ticket(new_ticket)

                                        # Notificar al técnico si fue asignado
                                        if new_ticket.technician_id and assigner:
                                            notifier.notify_ticket_assigned(new_ticket, assigner)
                                    except Exception as e:
                                        print(f"ERROR: No se pudo enviar la notificación por correo. Causa: {e}")

                                    table.rows = load_tickets()
                                    table.update()
                                    dialog.close()
                                except Exception as e:
                                    db_session.rollback()
                                    ui.notify(f"Error al crear el ticket: {e}", color='negative', multi_line=True)
                                finally:
                                    db_session.close()
                            
                            with ui.row().classes('w-full justify-end mt-4 gap-2 p-4'):
                                ui.button("Guardar", on_click=handle_save, color='primary')
                                ui.button("Cancelar", on_click=dialog.close)
                        dialog.open()
                    ui.button("Nuevo Ticket", on_click=open_new_ticket_dialog, icon='add').props('outline color=primary')

            columns = [
                {'name': 'id', 'label': 'ID', 'field': 'id', 'sortable': True},
                {'name': 'title', 'label': 'Título', 'field': 'title', 'align': 'left', 'style': 'white-space: normal; text-align: justify;'},
                {'name': 'description', 'label': 'Descripción', 'field': 'description', 'align': 'left', 'style': 'white-space: normal; text-align: justify;'},
                {'name': 'status', 'label': 'Estado', 'field': 'status', 'sortable': True},
                {'name': 'urgency', 'label': 'Urgencia', 'field': 'urgency', 'sortable': True},
                {'name': 'requester_name', 'label': 'Solicitante', 'field': 'requester_name', 'sortable': True},
                {'name': 'technician_name', 'label': 'Técnico', 'field': 'technician_name', 'sortable': True},
                {'name': 'location_name', 'label': 'Ubicación', 'field': 'location_name', 'sortable': True},
                {'name': 'created_at', 'label': 'Fecha Creación', 'field': 'created_at', 'sortable': True},
                {'name': 'actions', 'label': 'Acciones', 'align': 'right'},
            ]

            table = ui.table(columns=columns, rows=load_tickets(), row_key='id').classes('w-full')
            table.add_slot('body-cell-actions', '''
                <q-td :props="props">
                    <div class="flex items-center justify-end">
                        <q-btn flat round color="primary" icon="visibility" @click="() => $parent.$emit('view', props.row)"></q-btn>
                    </div>
                </q-td>
            ''')
            table.on('view', lambda e: ui.navigate.to(f'/ticket/{e.args["id"]}'))
