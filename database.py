
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from passlib.context import CryptContext
import csv
import os

from models import Base, User, UserRole, SLA, TicketUrgency, ITILCategory, ITILSubCategory, ProblemType, Location

# --- Configuración para SQLite (para desarrollo) ---
# DATABASE_URL = "sqlite:///./helpdeskoi.db"
# engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# --- Configuración para MariaDB/MySQL (para producción) ---
# Las variables se cargan desde el archivo .env al iniciar la aplicación en main.py
DB_USER = os.environ.get("DB_USER")
DB_PASSWORD = os.environ.get("DB_PASSWORD")
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT")
DB_NAME = os.environ.get("DB_NAME")

# Validar que todas las variables de entorno necesarias para la BD estén presentes
required_db_vars = {"DB_USER": DB_USER, "DB_PASSWORD": DB_PASSWORD, "DB_HOST": DB_HOST, "DB_PORT": DB_PORT, "DB_NAME": DB_NAME}
missing_vars = [key for key, value in required_db_vars.items() if value is None]
if missing_vars:
    raise ValueError(f"Faltan las siguientes variables de entorno de base de datos requeridas: {', '.join(missing_vars)}. Asegúrate de que el archivo .env esté configurado.")

DATABASE_URL = f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

itil_data = [
    {
        "category": "Soporte Técnico",
        "subcategories": [
            {
                "name": "Hardware",
                "problems": [
                    "Diagnóstico y Reparación de Hardware",
                    "Mantenimiento Preventivo y Correctivo",
                    "Instalación de Equipos (PCs, laptops, impresoras, escáneres)",
                    "Soporte de Periféricos (teclados, ratones, monitores)",
                    "Gestión de Inventario de Equipos",
                    "Actualización de Componentes (memoria RAM, discos duros)",
                    "Soporte de Dispositivos Móviles (tabletas, smartphones)",
                    "Accesorios y Repuestos",
                    "Desinstalación y Desecho de Equipos Obsoletos",
                    "Diagnóstico de Fallas de Energía y UPS",
                ]
            },
            {
                "name": "Software",
                "problems": [
                    "Soporte de Sistema Operativo (instalación, configuración y actualización)",
                    "Soporte de Aplicaciones (instalación, configuración, licenciamiento)",
                    "Soporte y Configuración de Software (PKi, Docuware, otros)",
                    "Actualización de Software y Parcheo",
                    "Soporte a Software de Seguridad (antivirus, firewall)",
                    "Configuración de Perfiles y Políticas de Usuario",
                    "Respaldo y Restauración de Información",
                    "Gestión de Accesos y Permisos",
                    "Resolución de Problemas de Compatibilidad",
                    "Soporte a Software de Productividad (Microsoft Office)",
                    "Optimización de Rendimiento de Software",
                ]
            }
        ]
    },
    {
        "category": "Análisis y Programación",
        "subcategories": [
            {
                "name": "Desarrollo",
                "problems": [
                    "Desarrollo de Aplicaciones Web",
                    "Desarrollo de Aplicaciones Móviles",
                    "Diseño y Programación de Base de Datos",
                    "Desarrollo de Aplicaciones de Escritorio",
                    "Automatización de Procesos",
                    "Integración de Sistemas",
                    "Gestión de APIs y Servicios Web",
                    "Desarrollo y Mantenimiento de Scripts (Python, PowerShell, Bash)",
                    "Documentación de Software",
                    "Pruebas de Software y Control de Calidad",
                    "Diseño de Arquitectura de Software",
                    "Gestión de Ciclo de Vida del Software (SDLC)",
                    "Análisis de Requerimientos y Diseño Funcional",
                    "Implementación de Seguridad en Desarrollo (OWASP, encriptación)",
                    "Optimización de Consultas y Gestión de Bases de Datos",
                ]
            }
        ]
    },
    {
        "category": "Infraestructura Tecnológica",
        "subcategories": [
            {
                "name": "Redes",
                "problems": [
                    "Instalación y Mantenimiento de Cableado Estructurado",
                    "Configuración de Equipos de Red (routers, switches)",
                    "Gestión de Direccionamiento IP y DHCP",
                    "Mantenimiento de Redes Inalámbricas (Wi-Fi, puntos de acceso)",
                    "Segmentación de Redes y VLANs",
                    "Gestión de Seguridad en Redes (firewall, VPN)",
                    "Monitoreo de Tráfico de Red",
                    "Diagnóstico y Resolución de Problemas de Conectividad",
                    "Configuración de Protocolos de Red (TCP/IP, DNS, VPN)",
                    "Soporte de Equipos de Red Industrial",
                    "Diseño y Optimización de Redes",
                ]
            },
            {
                "name": "Telefonía",
                "problems": [
                    "Instalación de Centralitas VoIP",
                    "Configuración de Teléfonos IP",
                    "Gestión de Sistemas de Mensajería de Voz",
                    "Implementación de Soluciones de Videoconferencia",
                    "Administración de Software de Telefonía",
                    "Soporte de Equipos de Telefonía y Audioconferencia",
                    "Integración de Telefonía con otros Sistemas",
                    "Gestión de Calidad de Voz en Redes (QoS)",
                ]
            },
            {
                "name": "Servidores",
                "problems": [
                    "Administración de Servidores Windows y Linux",
                    "Instalación y Configuración de Servidores Físicos y Virtuales",
                    "Gestión de Servicios en la Nube",
                    "Implementación y Mantenimiento de Active Directory",
                    "Administración de Servidores de Correo Electrónico",
                    "Respaldo y Recuperación de Servidores",
                    "Seguridad en Servidores",
                    "Monitoreo de Rendimiento de Servidores",
                    "Administración de Servidores Web",
                    "Gestión de Almacenamiento y RAID",
                    "Automatización y Orquestación de Infraestructura",
                ]
            }
        ]
    },
    {
        "category": "Gestión de Servicios y Soporte al Usuario",
        "subcategories": [
            {
                "name": "Gestión de Incidentes y Problemas",
                "problems": [
                    "Documentación de Incidentes y Problemas: registro de casos y soluciones aplicadas.",
                    "Gestión de Niveles de Servicio (SLA): monitoreo y cumplimiento de acuerdos de servicio.",
                    "Capacitación de Usuarios: formación y soporte preventivo para usuarios.",
                    "Gestión de Problemas y Root Cause Analysis (RCA): análisis de causas y resolución de problemas recurrentes.",
                    "Evaluación de Satisfacción del Usuario: encuestas y retroalimentación sobre el soporte.",
                ]
            }
        ]
    }
]

def populate_itil_categories():
    db = SessionLocal()
    try:
        if db.query(ITILCategory).first():
            # print("Las categorías ITIL ya han sido pobladas.")
            return

        print("Poblando categorías ITIL...")
        for category_data in itil_data:
            category = ITILCategory(name=category_data["category"])
            db.add(category)
            db.flush()

            for subcategory_data in category_data["subcategories"]:
                subcategory = ITILSubCategory(name=subcategory_data["name"], category_id=category.id)
                db.add(subcategory)
                db.flush()

                for problem_name in subcategory_data["problems"]:
                    problem_type = ProblemType(name=problem_name, subcategory_id=subcategory.id)
                    db.add(problem_type)
        
        db.commit()
        print("Categorías ITIL pobladas exitosamente.")

    except Exception as e:
        print(f"Error al poblar las categorías ITIL: {e}")
        db.rollback()
    finally:
        db.close()

def populate_locations():
    db = SessionLocal()
    try:
        if db.query(Location).first():
            # print("Las ubicaciones ya han sido pobladas.")
            return

        print("Poblando ubicaciones...")
        
        # Construir la ruta al archivo CSV relativa a este script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        csv_file_path = os.path.join(current_dir, 'Ubicaciones.csv')

        with open(csv_file_path, mode='r', encoding='utf-8-sig') as infile:
            reader = csv.reader(infile)
            next(reader, None)  # Omitir la cabecera
            for row in reader:
                if not row or not row[0]:  # Omitir filas vacías
                    continue
                name, description = row
                location = Location(name=name.strip(), description=description.strip())
                db.add(location)
        
        db.commit()
        print("Ubicaciones pobladas exitosamente.")
    except Exception as e:
        print(f"Error al poblar las ubicaciones: {e}")
        db.rollback()
    finally:
        db.close()

def init_db():
    # Crea todas las tablas
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Verifica si el usuario admin ya existe
        admin_user = db.query(User).filter(User.username == "helpdeskoi").first()
        if not admin_user:
            hashed_password = get_password_hash("50cvz856d8V#")
            new_admin = User(
                username="helpdeskoi",
                email="admin@helpdeskoi.local",
                password_hash=hashed_password,
                role=UserRole.ADMINISTRADOR,
                full_name="Admin HelpdeskOI",
                is_active=1
            )
            db.add(new_admin)
            print("Usuario administrador 'helpdeskoi' creado.")

        # Verifica y crea SLAs iniciales
        if db.query(SLA).count() == 0:
            slas = [
                SLA(urgency=TicketUrgency.BAJA, assignment_time_hours=24, resolution_time_hours=96),
                SLA(urgency=TicketUrgency.MEDIA, assignment_time_hours=8, resolution_time_hours=48),
                SLA(urgency=TicketUrgency.ALTA, assignment_time_hours=1, resolution_time_hours=8),
            ]
            db.add_all(slas)
            print("SLAs iniciales creados.")

        db.commit()
    finally:
        db.close()

    # Poblar categorías ITIL después de crear las tablas
    populate_itil_categories()

    # Poblar ubicaciones desde CSV
    populate_locations()
