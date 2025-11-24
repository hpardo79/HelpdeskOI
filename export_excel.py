import pandas as pd
import io
from datetime import datetime

def generate_excel_report(report_data: dict) -> bytes:
    """
    Genera un archivo Excel en memoria a partir de los datos del reporte.

    Args:
        report_data: Un diccionario que contiene todos los datos procesados para el reporte.

    Returns:
        Los bytes del archivo Excel generado.
    """
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Diccionario para almacenar los dataframes y poder ajustar las columnas después
        dataframes = {}
        
        # --- Hoja 1: Rendimiento de Técnicos ---
        if report_data.get('tech'):
            tech_rows = []
            for row in report_data['tech']:
                assigned_count = row['assigned_count']
                resolved_count = row['resolved_count']
                efectividad = f"{((resolved_count / assigned_count) * 100):.1f}%" if assigned_count > 0 else "N/A"
                tech_rows.append({
                    'Técnico': row['username'],
                    'Tickets Asignados': assigned_count,
                    'Tickets Resueltos': resolved_count,
                    'Efectividad %': efectividad
                })
            df_tech = pd.DataFrame(tech_rows)
            df_tech.to_excel(writer, sheet_name='Rendimiento_Tecnicos', index=False)
            dataframes['Rendimiento_Tecnicos'] = df_tech

        # --- Hoja 2: Cumplimiento de SLA ---
        if report_data.get('tech'):
            sla_rows = []
            for tech_row in report_data['tech']:
                tech_username = tech_row['username']
                assigned_count = tech_row['assigned_count']
                violation_count = report_data['tech_sla_violations'].get(tech_username, 0)
                percentage = f"{((violation_count / assigned_count) * 100):.1f}%" if assigned_count > 0 else "N/A"
                sla_rows.append({
                    'Técnico': tech_username,
                    'Tickets Fuera de SLA': violation_count,
                    'Total Asignados': assigned_count,
                    '% Fuera de SLA': percentage
                })
            df_sla = pd.DataFrame(sla_rows)
            df_sla.to_excel(writer, sheet_name='Cumplimiento_SLA', index=False)
            dataframes['Cumplimiento_SLA'] = df_sla

        # --- Hoja 3: Distribución de Carga ---
        if report_data.get('tech_distribution'):
            dist_rows = []
            for tech, rows in report_data['tech_distribution'].items():
                for row in rows:
                    dist_rows.append({
                        'Técnico': tech,
                        'Tipo de Problema': row.problem_name,
                        'Urgencia': row.urgency.value.title(),
                        'Cantidad': row.ticket_count
                    })
            df_dist = pd.DataFrame(dist_rows)
            df_dist.to_excel(writer, sheet_name='Distribucion_Carga', index=False)
            dataframes['Distribucion_Carga'] = df_dist

        # --- Hoja 4: Incidencias por Tipo ---
        if report_data.get('problem'):
            df_problem = pd.DataFrame([{'Tipo de Problema': r.name, 'Cantidad': r.ticket_count} for r in report_data['problem']])
            df_problem.to_excel(writer, sheet_name='Incidencias_por_Tipo', index=False)
            dataframes['Incidencias_por_Tipo'] = df_problem

        # --- Hoja 5: Incidencias por Ubicación ---
        if report_data.get('location'):
            df_location = pd.DataFrame([{'Ubicación': r.description, 'Cantidad': r.ticket_count} for r in report_data['location']])
            df_location.to_excel(writer, sheet_name='Incidencias_por_Ubicacion', index=False)
            dataframes['Incidencias_por_Ubicacion'] = df_location

        # --- Hoja 6: Resumen Ubicación-Problema ---
        if report_data.get('location_problem'):
            df_loc_prob = pd.DataFrame([{
                'Ubicación': r.location_description,
                'Tipo de Problema': r.problem_type_name,
                'Cantidad': r.ticket_count
            } for r in report_data['location_problem']])
            df_loc_prob.to_excel(writer, sheet_name='Resumen_Ubicacion_Problema', index=False)
            dataframes['Resumen_Ubicacion_Problema'] = df_loc_prob

        # --- Hoja 7: Volumen Diario ---
        all_dates = sorted(list(set(
            [row.creation_day for row in report_data.get('volume', [])] +
            [row.assignment_day for row in report_data.get('assigned', [])] +
            [row.rejection_day for row in report_data.get('rejected', [])] +
            [row.resolution_day for row in report_data.get('resolved_vol', [])]
        )))

        if all_dates:
            created_counts = {row.creation_day: row.daily_count for row in report_data.get('volume', [])}
            assigned_counts = {row.assignment_day: row.daily_count for row in report_data.get('assigned', [])}
            rejected_counts = {row.rejection_day: row.daily_count for row in report_data.get('rejected', [])}
            resolved_counts = {row.resolution_day: row.daily_count for row in report_data.get('resolved_vol', [])}

            volume_rows = []
            for d in all_dates:
                date_str = (datetime.strptime(d, '%Y-%m-%d') if isinstance(d, str) else d).strftime('%Y-%m-%d')
                volume_rows.append({
                    'Fecha': date_str,
                    'Creados': created_counts.get(d, 0),
                    'Asignados': assigned_counts.get(d, 0),
                    'Resueltos': resolved_counts.get(d, 0),
                    'Rechazados': rejected_counts.get(d, 0)
                })
            
            df_volume = pd.DataFrame(volume_rows)
            df_volume.to_excel(writer, sheet_name='Volumen_Diario', index=False)
            dataframes['Volumen_Diario'] = df_volume

        # --- Ajuste automático del ancho de las columnas ---
        for sheet_name, df in dataframes.items():
            worksheet = writer.sheets[sheet_name]
            for idx, col in enumerate(df):  # iterar sobre los nombres de las columnas del dataframe
                series = df[col]
                max_len = max((
                    series.astype(str).map(len).max(),  # longitud del dato más largo
                    len(str(series.name))  # longitud del encabezado de la columna
                )) + 2  # un poco de espacio extra
                worksheet.set_column(idx, idx, max_len)

    return output.getvalue()