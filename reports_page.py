from nicegui import app, ui
from sqlalchemy import func
from datetime import datetime, timedelta, timezone

from database import SessionLocal
from models import Ticket, User, ProblemType, UserRole, TicketStatus, Location, TicketUpdate, TicketUrgency
from main_layout import create_main_layout
from export_excel import generate_excel_report

def get_available_years():
    db = SessionLocal()
    try:
        years_query = db.query(func.extract('year', Ticket.created_at)).distinct().order_by(func.extract('year', Ticket.created_at).desc()).all()
        return [year[0] for year in years_query if year[0] is not None]
    finally:
        db.close()

class ReportPage:
    def __init__(self):
        self.report_data = {
            'tech': [], 'problem': [], 'volume': [],
            'location': [], 'location_problem': [], 'start_date': '', 'end_date': '',
            'assigned': [], 'rejected': [], 'resolved_vol': [],
            'tech_distribution': {},  # Para la nueva métrica de distribución
            'tech_sla_violations': {} # Para la nueva métrica de SLA
        }
        self.year_from_selector = None
        self.month_from_selector = None
        self.year_to_selector = None
        self.month_to_selector = None
        self.reports_container = None

    def get_report_data(self, start_date: datetime, end_date: datetime):
        db = SessionLocal()
        try: # Tickets resueltos en el período
            resolved_query = db.query(
                User.username,
                func.count(Ticket.id).label('resolved_count')
            ).join(Ticket, User.id == Ticket.technician_id).filter(
                Ticket.status == TicketStatus.RESUELTO,
                Ticket.resolved_at.isnot(None),
                Ticket.assigned_at.isnot(None),
                Ticket.resolved_at >= start_date,
                Ticket.resolved_at < end_date
            ).group_by(User.username)
            resolved_data = {row.username: row for row in resolved_query.all()}

            # Tickets asignados en el período
            assigned_query = db.query(
                User.username,
                func.count(Ticket.id).label('assigned_count')
            ).join(Ticket, User.id == Ticket.technician_id).filter(
                Ticket.assigned_at.isnot(None),
                Ticket.assigned_at >= start_date,
                Ticket.assigned_at < end_date
            ).group_by(User.username)
            assigned_data = {row.username: row for row in assigned_query.all()}

            # Combinar datos de tickets resueltos y asignados
            all_techs = sorted(list(set(resolved_data.keys()) | set(assigned_data.keys())))
            tech_performance = []
            for tech_username in all_techs:
                resolved_info = resolved_data.get(tech_username)
                assigned_info = assigned_data.get(tech_username)
                
                tech_performance.append({
                    'username': tech_username,
                    'resolved_count': resolved_info.resolved_count if resolved_info else 0,
                    'assigned_count': assigned_info.assigned_count if assigned_info else 0,
                })

            # Análisis de problemas (basado en la fecha de creación)
            problem_query = db.query(
                ProblemType.name,
                func.count(Ticket.id).label('ticket_count')
            ).join(ProblemType, Ticket.problem_type_id == ProblemType.id).filter(
                Ticket.created_at >= start_date,
                Ticket.created_at < end_date
            )
            problem_analysis = problem_query.group_by(ProblemType.name).order_by(func.count(Ticket.id).desc()).all()

            # Volumen de tickets (basado en la fecha de creación)
            volume_query = db.query(
                func.date(Ticket.created_at).label('creation_day'),
                func.count(Ticket.id).label('daily_count')
            ).filter(
                Ticket.created_at >= start_date,
                Ticket.created_at < end_date
            )
            ticket_volume = volume_query.group_by('creation_day').order_by('creation_day').all()

            # Tickets por ubicación (basado en la fecha de creación)
            location_query = db.query(
                Location.description,
                func.count(Ticket.id).label('ticket_count')
            ).join(Ticket, Location.id == Ticket.location_id).filter(
                Ticket.created_at >= start_date,
                Ticket.created_at < end_date
            ).group_by(Location.description).order_by(func.count(Ticket.id).desc())
            location_analysis = location_query.all()

            # Resumen por Ubicación y Tipo de Problema
            location_problem_query = db.query(
                Location.description.label('location_description'),
                ProblemType.name.label('problem_type_name'),
                func.count(Ticket.id).label('ticket_count')
            ).join(Ticket, Location.id == Ticket.location_id
            ).join(ProblemType, Ticket.problem_type_id == ProblemType.id
            ).filter(
                Ticket.created_at >= start_date,
                Ticket.created_at < end_date,
                Ticket.location_id.isnot(None),
                Ticket.problem_type_id.isnot(None)
            ).group_by(
                Location.description, ProblemType.name
            ).order_by(
                Location.description, func.count(Ticket.id).desc()
            )
            location_problem_data = location_problem_query.all()

            # Tickets Asignados por día
            assigned_volume_query = db.query(
                func.date(Ticket.assigned_at).label('assignment_day'),
                func.count(Ticket.id).label('daily_count')
            ).filter(
                Ticket.assigned_at >= start_date,
                Ticket.assigned_at < end_date
            ).group_by('assignment_day').order_by('assignment_day')
            assigned_volume = assigned_volume_query.all()

            # Tickets Rechazados por día
            rejected_volume_query = db.query(
                func.date(TicketUpdate.timestamp).label('rejection_day'),
                func.count(func.distinct(Ticket.id)).label('daily_count')
            ).join(
                TicketUpdate, Ticket.id == TicketUpdate.ticket_id
            ).filter(
                TicketUpdate.comment.like('Ticket Rechazado. Motivo: %'),
                TicketUpdate.timestamp >= start_date,
                TicketUpdate.timestamp < end_date
            ).group_by('rejection_day').order_by('rejection_day')
            rejected_volume = rejected_volume_query.all()

            # Tickets Resueltos por día
            resolved_volume_query = db.query(
                func.date(Ticket.resolved_at).label('resolution_day'),
                func.count(Ticket.id).label('daily_count')
            ).filter(
                Ticket.status == TicketStatus.RESUELTO,
                Ticket.resolved_at >= start_date,
                Ticket.resolved_at < end_date
            ).group_by('resolution_day').order_by('resolution_day')
            resolved_volume = resolved_volume_query.all()

            # Nueva métrica: Distribución por técnico (categoría/prioridad)
            tech_distribution_query = db.query(
                User.username,
                ProblemType.name.label('problem_name'),
                Ticket.urgency,
                func.count(Ticket.id).label('ticket_count')
            ).join(Ticket, User.id == Ticket.technician_id
            ).join(ProblemType, Ticket.problem_type_id == ProblemType.id
            ).filter(
                Ticket.assigned_at >= start_date,
                Ticket.assigned_at < end_date,
                Ticket.technician_id.isnot(None),
                Ticket.problem_type_id.isnot(None)
            ).group_by(
                User.username, ProblemType.name, Ticket.urgency
            ).order_by(
                User.username, func.count(Ticket.id).desc()
            )
            tech_distribution_data = tech_distribution_query.all()

            # Nueva métrica: Tiempos fuera de SLA por técnico
            sla_violations_query = db.query(
                User.username,
                func.count(Ticket.id).label('violation_count')
            ).join(Ticket, User.id == Ticket.technician_id
            ).filter(
                Ticket.sla_violation_sent == True,
                Ticket.assigned_at >= start_date,
                Ticket.assigned_at < end_date
            ).group_by(User.username)
            sla_violations_data = {row.username: row.violation_count for row in sla_violations_query.all()}

            return tech_performance, problem_analysis, ticket_volume, location_analysis, location_problem_data, assigned_volume, rejected_volume, resolved_volume, tech_distribution_data, sla_violations_data
        finally:
            db.close()

    def update_reports(self):
        self.reports_container.clear()

        from_year = self.year_from_selector.value
        from_month = self.month_from_selector.value
        to_year = self.year_to_selector.value
        to_month = self.month_to_selector.value

        try:
            start_date = datetime(from_year, from_month, 1)
            
            if to_month == 12:
                end_date = datetime(to_year + 1, 1, 1)
            else:
                end_date = datetime(to_year, to_month + 1, 1)

            if start_date >= end_date:
                ui.notify('La fecha de inicio debe ser anterior a la fecha de fin.', color='warning')
                return

        except (ValueError, TypeError):
            ui.notify('Por favor, seleccione valores válidos para las fechas.', color='warning')
            return

        tech_data, problem_data, volume_data, location_data, location_problem_data, assigned_data, rejected_data, resolved_vol_data, tech_distribution_data, sla_violations_data = self.get_report_data(start_date, end_date)

        self.report_data['tech'] = tech_data
        self.report_data['problem'] = problem_data
        self.report_data['volume'] = volume_data
        self.report_data['location'] = location_data
        self.report_data['location_problem'] = location_problem_data
        self.report_data['assigned'] = assigned_data
        self.report_data['rejected'] = rejected_data
        self.report_data['resolved_vol'] = resolved_vol_data

        # Procesar y almacenar datos para las nuevas métricas
        from collections import defaultdict
        tech_dist_grouped = defaultdict(list)
        for row in tech_distribution_data:
            tech_dist_grouped[row.username].append(row)
        self.report_data['tech_distribution'] = tech_dist_grouped
        self.report_data['tech_sla_violations'] = sla_violations_data

        self.report_data['start_date'] = start_date.strftime('%Y-%m-%d')
        self.report_data['end_date'] = (end_date - timedelta(days=1)).strftime('%Y-%m-%d')

        with self.reports_container:
            with ui.card().classes('w-full rounded-xl shadow-md p-6'):
                ui.label("Rendimiento de Técnicos").classes('text-xl font-semibold text-gray-700')
                with ui.column().classes('w-full gap-6 mt-4'):
                    ui.table(**{
                        'columns': [
                            {'name': 'tecnico', 'label': 'Técnico', 'field': 'tecnico', 'align': 'left'},
                            {'name': 'asignados', 'label': 'Tickets Asignados', 'field': 'asignados'},
                            {'name': 'resueltos', 'label': 'Tickets Resueltos', 'field': 'resueltos'},
                            {'name': 'efectividad', 'label': 'Efectividad %', 'field': 'efectividad'}
                        ],
                        'rows': [
                            {
                                'tecnico': row['username'],
                                'asignados': row['assigned_count'],
                                'resueltos': row['resolved_count'],
                                'efectividad': f"{((row['resolved_count'] / row['assigned_count']) * 100):.1f}%" if row['assigned_count'] > 0 else 'N/A'
                            }
                            for row in tech_data
                        ]
                    }, title="Desempeño General").classes('w-full')

                    # Métrica: Distribución por técnico
                    with ui.column().classes('w-full gap-2 mt-6'):
                        ui.label("Distribución de Carga de Trabajo por Técnico").classes('text-lg font-semibold text-gray-600')
                        if self.report_data['tech_distribution']:
                            for tech_username, dist_rows in self.report_data['tech_distribution'].items():
                                alta_count = sum(r.ticket_count for r in dist_rows if r.urgency == TicketUrgency.ALTA)
                                media_count = sum(r.ticket_count for r in dist_rows if r.urgency == TicketUrgency.MEDIA)
                                baja_count = sum(r.ticket_count for r in dist_rows if r.urgency == TicketUrgency.BAJA)
                                total_for_tech = alta_count + media_count + baja_count

                                expansion_title = (f"{tech_username} (Total: {total_for_tech} | "
                                                   f"Alta: {alta_count}, Media: {media_count}, Baja: {baja_count})")

                                with ui.expansion(expansion_title, icon='work').classes('w-full bg-gray-50 rounded-lg'):
                                    ui.table(columns=[
                                        {'name': 'problema', 'label': 'Tipo de Problema', 'field': 'problema', 'align': 'left'},
                                        {'name': 'urgencia', 'label': 'Urgencia', 'field': 'urgencia'},
                                        {'name': 'cantidad', 'label': 'Cantidad', 'field': 'cantidad'},
                                    ], rows=[
                                        {
                                            'problema': row.problem_name,
                                            'urgencia': row.urgency.value.title(),
                                            'cantidad': row.ticket_count
                                        } for row in dist_rows
                                    ]).classes('w-full')
                        else:
                            ui.label("No hay datos de distribución para este período.").classes('text-gray-500 p-4')

                    # Métrica: Tiempos fuera de SLA por técnico
                    with ui.column().classes('w-full gap-2 mt-6'):
                        ui.label("Cumplimiento de SLA por Técnico").classes('text-lg font-semibold text-gray-600')
                        sla_rows = []
                        for tech_row in self.report_data['tech']:
                            tech_username = tech_row['username']
                            assigned_count = tech_row['assigned_count']
                            violation_count = self.report_data['tech_sla_violations'].get(tech_username, 0)
                            
                            if assigned_count > 0:
                                percentage = f"{((violation_count / assigned_count) * 100):.1f}%"
                            else:
                                percentage = "N/A"
                            
                            sla_rows.append({
                                'tecnico': tech_username,
                                'violaciones': violation_count,
                                'total_asignados': assigned_count,
                                'porcentaje_violacion': percentage
                            })
                        
                        ui.table(columns=[{'name': 'tecnico', 'label': 'Técnico', 'field': 'tecnico', 'align': 'left'}, {'name': 'violaciones', 'label': 'Tickets Fuera de SLA', 'field': 'violaciones'}, {'name': 'total_asignados', 'label': 'Total Asignados', 'field': 'total_asignados'}, {'name': 'porcentaje_violacion', 'label': '% Fuera de SLA', 'field': 'porcentaje_violacion'}], rows=sla_rows).classes('w-full')


            with ui.row().classes('w-full grid grid-cols-1 md:grid-cols-2 gap-6'):
                with ui.card().classes('w-full rounded-xl shadow-md p-6'):
                    ui.label("Análisis de Incidencias").classes('text-xl font-semibold text-gray-700')
                    if problem_data:
                        ui.echart({
                            'title': {'text': 'Tickets por Tipo de Problema', 'left': 'center'},
                            'tooltip': {'trigger': 'item', 'formatter': '{b}: {c} ({d}%)'},
                            'series': [{
                                'name': 'Tickets',
                                'type': 'pie',
                                'radius': ['40%', '70%'],
                                'label': {'show': True, 'formatter': '{b}\n{c}', 'position': 'outside'},
                                'labelLine': {'show': True},
                                'data': [{'value': row.ticket_count, 'name': row.name} for row in problem_data],
                                'emphasis': {
                                    'itemStyle': {
                                        'shadowBlur': 10,
                                        'shadowOffsetX': 0,
                                        'shadowColor': 'rgba(0, 0, 0, 0.5)'
                                    }
                                }
                            }]
                        }).classes('w-full h-96')
                    else:
                        ui.label("No hay datos de incidencias en este período.").classes('text-gray-500')

                with ui.card().classes('w-full rounded-xl shadow-md p-6'):
                    ui.label("Tickets por Ubicación").classes('text-xl font-semibold text-gray-700')
                    if location_data:
                         ui.echart({
                            'title': {'text': 'Tickets por Ubicación', 'left': 'center'},
                            'tooltip': {'trigger': 'item', 'formatter': '{b}: {c} ({d}%)'},
                            'series': [{
                                'name': 'Tickets',
                                'type': 'pie',
                                'radius': ['40%', '70%'],
                                'label': {'show': True, 'formatter': '{b}\n{c}', 'position': 'outside'},
                                'labelLine': {'show': True},
                                'data': [{'value': row.ticket_count, 'name': row.description} for row in location_data],
                                'emphasis': {
                                    'itemStyle': {
                                        'shadowBlur': 10,
                                        'shadowOffsetX': 0,
                                        'shadowColor': 'rgba(0, 0, 0, 0.5)'
                                    }
                                }
                            }]
                        }).classes('w-full h-96')
                    else:
                        ui.label("No hay datos de tickets por ubicación en este período.").classes('text-gray-500')

            with ui.card().classes('w-full rounded-xl shadow-md p-6'):
                ui.label("Resumen por Ubicación y Tipo de Problema").classes('text-xl font-semibold text-gray-700')
                if location_problem_data:
                    from collections import defaultdict
                    grouped_data = defaultdict(list)
                    for row in location_problem_data:
                        grouped_data[row.location_description].append({
                            'problem': row.problem_type_name,
                            'count': row.ticket_count
                        })

                    with ui.column().classes('w-full gap-2 mt-4'):
                        for location, problems in grouped_data.items():
                            total_tickets_location = sum(p['count'] for p in problems)
                            with ui.expansion(f'{location} ({total_tickets_location} tickets)', icon='location_on').classes('w-full bg-gray-50 rounded-lg'):
                                with ui.list().classes('w-full'):
                                    for problem in problems:
                                        with ui.item().classes('w-full'):
                                            with ui.item_section():
                                                ui.label(problem['problem'])
                                            with ui.item_section().props('side'):
                                                ui.badge(problem['count'], color='blue-9')
                else:
                    ui.label("No hay datos para este resumen en el período seleccionado.").classes('text-gray-500')

            with ui.card().classes('w-full rounded-xl shadow-md p-6'):
                ui.label("Volumen de Tickets por Día").classes('text-xl font-semibold text-gray-700')
                if volume_data:
                    all_dates = sorted(list(set(
                        [row.creation_day for row in volume_data] +
                        [row.assignment_day for row in assigned_data] +
                        [row.rejection_day for row in rejected_data] +
                        [row.resolution_day for row in resolved_vol_data]
                    )))

                    dates_str = [(datetime.strptime(d, '%Y-%m-%d') if isinstance(d, str) else d).strftime('%d/%m') for d in all_dates]
                    
                    created_counts = {row.creation_day: row.daily_count for row in volume_data}
                    assigned_counts = {row.assignment_day: row.daily_count for row in assigned_data}
                    rejected_counts = {row.rejection_day: row.daily_count for row in rejected_data}
                    resolved_counts = {row.resolution_day: row.daily_count for row in resolved_vol_data}

                    created_series = [created_counts.get(d, 0) for d in all_dates]
                    assigned_series = [assigned_counts.get(d, 0) for d in all_dates]
                    rejected_series = [rejected_counts.get(d, 0) for d in all_dates]
                    resolved_series = [resolved_counts.get(d, 0) for d in all_dates]

                    ui.echart({
                        'tooltip': {'trigger': 'axis'},
                        'legend': {'data': ['Creados', 'Asignados', 'Resueltos', 'Rechazados'], 'bottom': 10},
                        'xAxis': {'type': 'category', 'data': dates_str},
                        'yAxis': {'type': 'value'},
                        'series': [
                            {
                                'name': 'Creados', 'type': 'line', 'data': created_series, 'smooth': True,
                                'itemStyle': {'color': '#3B82F6'}, # Azul
                                'areaStyle': {
                                    'color': {'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                                              'colorStops': [{'offset': 0, 'color': '#60A5FA'}, {'offset': 1, 'color': 'rgba(255,255,255,0)'}]}
                                }
                            },
                            {
                                'name': 'Asignados', 'type': 'line', 'data': assigned_series, 'smooth': True,
                                'itemStyle': {'color': '#F59E0B'}, # Ámbar
                                'areaStyle': {
                                    'color': {'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                                              'colorStops': [{'offset': 0, 'color': '#FBBF24'}, {'offset': 1, 'color': 'rgba(255,255,255,0)'}]}
                                }
                            },
                            {
                                'name': 'Resueltos', 'type': 'line', 'data': resolved_series, 'smooth': True,
                                'itemStyle': {'color': '#22C55E'}, # Verde
                                'areaStyle': {
                                    'color': {'type': 'linear', 'x': 0, 'y': 0, 'x2': 0, 'y2': 1,
                                              'colorStops': [{'offset': 0, 'color': '#4ADE80'}, {'offset': 1, 'color': 'rgba(255,255,255,0)'}]}
                                }
                            },
                            {
                                'name': 'Rechazados', 'type': 'line', 'data': rejected_series, 'smooth': True,
                                'itemStyle': {'color': '#EF4444'}, # Rojo
                            }
                        ]
                    })
                else:
                    ui.label("No hay datos de volumen de tickets en este período.").classes('text-gray-500')

    def create(self):
        if not app.storage.user.get('authenticated', False) or app.storage.user.get('role') not in [UserRole.ADMINISTRADOR.value, UserRole.SUPERVISOR.value, UserRole.MONITOR.value]:
            return ui.navigate.to('/')

        create_main_layout()
        with ui.column().classes('w-full p-4 md:p-6 lg:p-8 gap-6'):
            ui.label("Página de Reportes").classes('text-2xl font-bold text-gray-800')

            with ui.card().classes('w-full rounded-xl shadow-md'):
                with ui.row().classes('w-full items-center p-4 gap-8'):
                    ui.label("Filtros:").classes('text-lg font-semibold')
                    
                    available_years = get_available_years()
                    current_year = datetime.now().year
                    if not available_years:
                        available_years.append(current_year)

                    months = {
                        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
                        5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto', 9: 'Septiembre',
                        10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
                    }

                    with ui.row().classes('items-center gap-2'):
                        ui.label("De:").classes('font-semibold')
                        self.year_from_selector = ui.select(available_years, label="Año", value=current_year).props('filled dense bg-white min-w-[120px]')
                        self.month_from_selector = ui.select(months, label="Mes", value=datetime.now().month).props('filled dense bg-white min-w-[120px]')

                    with ui.row().classes('items-center gap-2'):
                        ui.label("Hasta:").classes('font-semibold')
                        self.year_to_selector = ui.select(available_years, label="Año", value=current_year).props('filled dense bg-white min-w-[120px]')
                        self.month_to_selector = ui.select(months, label="Mes", value=datetime.now().month).props('filled dense bg-white min-w-[120px]')

                    with ui.row().classes('items-center gap-2 self-center'):
                        ui.button('Actualizar', on_click=self.update_reports).props('color=primary')
                        
                        def handle_export():
                            if not self.report_data.get('tech'):
                                ui.notify("No hay datos para exportar. Por favor, genere un reporte primero.", color='warning')
                                return
                            file_content = generate_excel_report(self.report_data)
                            filename = f"Reporte_HelpdeskOI_{self.report_data['start_date']}_a_{self.report_data['end_date']}.xlsx"
                            ui.download(file_content, filename)

                        ui.button('Exportar a Excel', on_click=handle_export, icon='file_download').props('color=positive outline')

            self.reports_container = ui.column().classes('w-full gap-6')
            
            self.update_reports()

@ui.page('/reports')
def reports_page():
    ReportPage().create()
