from nicegui import app, ui
from database import SessionLocal
from models import Ticket, User, UserRole, TicketStatus
from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload
from datetime import datetime
from datetime_utils import to_local_time, format_utc_time

def search_page():
    with ui.column().classes('w-full items-center'):
        with ui.row().classes('w-full justify-center items-center gap-2'):
            search_term_input = ui.input(placeholder='Introducir consulta de búsqueda').classes('w-1/2')
            search_button = ui.button('Buscar', icon='search')

        ui.separator().classes('w-full my-4')
        ui.label('Resultados de la búsqueda').classes('text-xl mt-4')

        results_table = ui.table(columns=[
            {'name': 'id', 'label': 'ID', 'field': 'id', 'sortable': True},
            {'name': 'title', 'label': 'Título', 'field': 'title', 'align': 'left', 'style': 'white-space: normal; text-align: justify;'},
            {'name': 'description', 'label': 'Descripción', 'field': 'description', 'align': 'left', 'style': 'white-space: normal; text-align: justify;'},
            {'name': 'status', 'label': 'Estatus', 'field': 'status', 'sortable': True},
            {'name': 'urgency', 'label': 'Urgencia', 'field': 'urgency', 'sortable': True},
            {'name': 'creator_name', 'label': 'Creado por', 'field': 'creator_name', 'sortable': True},
            {'name': 'technician_name', 'label': 'Técnico', 'field': 'technician_name', 'sortable': True},
            {'name': 'created_at', 'label': 'Fecha Creación', 'field': 'created_at', 'sortable': True},
            {'name': 'actions', 'label': 'Acciones', 'align': 'right'},
        ], rows=[], row_key='id').classes('w-full')
        results_table.add_slot('body-cell-actions', '''
            <q-td :props="props">
                <div class="flex items-center justify-end">
                    <q-btn flat round color="primary" icon="visibility" @click="() => $parent.$emit('view', props.row)"></q-btn>
                </div>
            </q-td>
        ''')
        results_table.on('view', lambda e: ui.navigate.to(f'/ticket/{e.args["id"]}'))
    def perform_search():
        term = search_term_input.value
        if not term:
            ui.notify('Introduzca un término de búsqueda.', color='warning')
            results_table.rows = []
            results_table.update()
            return

        db = SessionLocal()
        try:
            role = app.storage.user.get('role')
            user_id = app.storage.user.get('id')

            # Construir la base de la consulta
            query = db.query(Ticket).options(
                joinedload(Ticket.creator),
                joinedload(Ticket.technician),
                joinedload(Ticket.problem_type)
            )

            # Aplicar filtro de visibilidad por rol
            if role == UserRole.TECNICO.value:
                query = query.filter(Ticket.technician_id == user_id)
            elif role == UserRole.AUTOSERVICIO.value:
                query = query.filter(Ticket.creator_id == user_id)

            # Construir las condiciones de búsqueda
            search_conditions = [
                Ticket.title.ilike(f'%{term}%'),
                Ticket.description.ilike(f'%{term}%')
            ]

            # Añadir búsqueda por estado (status)
            status_values = {s.value.lower(): s for s in TicketStatus}
            if term.lower() in status_values:
                search_conditions.append(Ticket.status == status_values[term.lower()])

            try:
                ticket_id = int(term)
                search_conditions.append(Ticket.id == ticket_id)
            except ValueError:
                # Si no es un ID, intentar interpretar como fecha
                try:
                    search_date = datetime.strptime(term, '%Y-%m-%d').date()
                    search_conditions.append(func.date(Ticket.created_at) == search_date)
                except ValueError:
                    pass # No es un ID ni una fecha válida, se buscará solo en texto.

            # Aplicar todas las condiciones con OR y ordenar
            tickets = query.filter(or_(*search_conditions)).order_by(Ticket.created_at.desc()).all()

            results_table.rows = [{
                'id': t.id,
                'title': t.title,
                'description': t.description,
                'status': t.status.value,
                'urgency': t.urgency.value if t.urgency else 'Unclassified',
                'creator_name': t.creator.username if t.creator else 'N/A',
                'technician_name': t.technician.username if t.technician else 'Unassigned',
                'created_at': to_local_time(t.created_at),
            } for t in tickets]
            results_table.update()
            if not tickets:
                ui.notify('No se encontraron entradas que coincidan con tu búsqueda.', color='info')

        except Exception as e:
            ui.notify(f'Error durante la búsqueda: {e}', color='negative')
        finally:
            db.close()

    search_term_input.on('keydown.enter', perform_search)
    search_button.on('click', perform_search)
