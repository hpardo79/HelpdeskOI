# HelpdeskOI

HelpdeskOI es una aplicación de mesa de ayuda (Helpdesk) moderna y eficiente diseñada para departamentos de TI. Permite la gestión integral de tickets de soporte, usuarios, inventario de ubicaciones y seguimiento de SLAs, todo a través de una interfaz web intuitiva y responsiva.

## 🚀 Características Principales

### Gestión de Tickets
*   **Ciclo de Vida Completo:** Creación, asignación, seguimiento, resolución y cierre de tickets.
*   **Clasificación ITIL:** Categorización multinivel (Categoría > Subcategoría > Tipo de Problema) para una mejor organización.
*   **Gestión de Estados:** Flujos de trabajo claros con estados como Nuevo, Asignado, En Proceso, Resuelto, Cerrado y Rechazado.
*   **Historial de Eventos:** Registro detallado de todas las acciones y comentarios en cada ticket.
*   **Priorización:** Asignación de urgencia (Baja, Media, Alta) y SLAs asociados.

### Automatización e Integración
*   **Creación por Correo Electrónico:** Convierte automáticamente los correos entrantes en tickets de soporte.
*   **Notificaciones:** Envío automático de correos electrónicos a técnicos y usuarios sobre actualizaciones, asignaciones y resoluciones.
*   **Monitoreo de SLAs:** Alertas automáticas cuando los tiempos de respuesta o resolución están por exceder los límites definidos.

### Roles y Seguridad
*   **Control de Acceso Basado en Roles (RBAC):**
    *   **Administrador:** Acceso total a configuraciones y gestión de usuarios.
    *   **Supervisor:** Gestión de tickets, asignaciones y reportes.
    *   **Técnico:** Atención y resolución de tickets asignados.
    *   **Monitor:** Visualización de dashboards y estados.
    *   **Autoservicio:** Usuarios finales que pueden crear y ver sus propios tickets.
*   **Seguridad:** Autenticación robusta con hashing de contraseñas y gestión de sesiones segura.

### Interfaz y Experiencia de Usuario
*   **Diseño Moderno:** Interfaz limpia y responsiva construida con **NiceGUI** y estilizada con **TailwindCSS**.
*   **Dashboards Dinámicos:** Vistas personalizadas según el rol del usuario con métricas clave y gráficos.
*   **Búsqueda Avanzada:** Herramientas para localizar tickets rápidamente por diversos criterios.

## 🛠 Tecnologías Utilizadas

*   **Lenguaje:** Python 3.x
*   **Framework Web:** [NiceGUI](https://nicegui.io/) (basado en FastAPI/Vue.js)
*   **Base de Datos:** SQLAlchemy (ORM) con soporte para SQLite (desarrollo) y MariaDB/MySQL (producción).
*   **Estilos:** TailwindCSS
*   **Otras Librerías:**
    *   `pandas` & `xlsxwriter`: Generación de reportes y exportación a Excel.
    *   `passlib` & `bcrypt`: Seguridad y hashing.
    *   `python-dotenv`: Gestión de variables de entorno.
    *   `imaplib`: Integración con correo electrónico.

## 📋 Requisitos Previos

*   Python 3.8 o superior.
*   Servidor de base de datos MariaDB (opcional para desarrollo, recomendado para producción).

## 🔧 Instalación y Configuración

1.  **Clonar el repositorio:**
    ```bash
    git clone <url-del-repositorio>
    cd helpdeskoi
    ```

2.  **Crear y activar un entorno virtual:**
    ```bash
    python -m venv .venv
    # En Linux/Mac:
    source .venv/bin/activate
    # En Windows:
    .venv\Scripts\activate
    ```

3.  **Instalar dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configurar variables de entorno:**
    Crea un archivo `.env` basado en `.env.example` y configura tus credenciales:
    ```env
    DATABASE_URL=sqlite:///./helpdeskoi.db  # O conexión a MariaDB
    STORAGE_SECRET=tu_clave_secreta_para_sesiones
    HELPDESKOI_KEY=tu_clave_de_encriptacion
    ```

5.  **Inicializar la base de datos:**
    La aplicación creará automáticamente las tablas y un usuario administrador por defecto al iniciarse por primera vez si no existen.

## ▶️ Ejecución

Para iniciar la aplicación en modo desarrollo:

```bash
python main.py
```

La aplicación estará disponible en `http://localhost:8080` (o el puerto configurado).

## 📂 Estructura del Proyecto

*   `main.py`: Punto de entrada de la aplicación y definición de rutas.
*   `models.py`: Definición de modelos de base de datos (ORM).
*   `database.py`: Configuración de conexión a base de datos.
*   `auth.py`: Lógica de autenticación y login.
*   `mail_reader.py`: Servicio de lectura de correos para creación de tickets.
*   `dashboard.py`: Lógica y componentes de los tableros de control.
*   `reports_page.py`: Generación de reportes y gráficos.
*   `notification_manager.py`: Sistema de envío de notificaciones.
