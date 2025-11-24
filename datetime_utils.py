from datetime import datetime, timezone
import pytz

def to_local_time(utc_dt: datetime, target_tz: str = 'America/Panama') -> str:
    """
    Convierte una fecha y hora (datetime) en formato UTC a una cadena de texto en la zona horaria local (por defecto, Panamá).
    """
    if utc_dt is None:
        return 'N/A'
    
    # Asegurarse de que el datetime de entrada sea consciente de la zona horaria UTC
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    else:
        utc_dt = utc_dt.astimezone(timezone.utc)
    
    try:
        panama_tz = pytz.timezone(target_tz)
        local_dt = utc_dt.astimezone(panama_tz)
        return local_dt.strftime('%Y-%m-%d %H:%M')
    except pytz.UnknownTimeZoneError:
        # Fallback si la zona horaria no es válida
        return utc_dt.strftime('%Y-%m-%d %H:%M (UTC)')

def format_utc_time(utc_dt: datetime) -> str:
    """
    Formatea una fecha y hora (datetime) en formato UTC a una cadena de texto, añadiendo el sufijo (UTC).
    """
    if utc_dt is None:
        return 'N/A'
    return utc_dt.strftime('%Y-%m-%d %H:%M (UTC)')