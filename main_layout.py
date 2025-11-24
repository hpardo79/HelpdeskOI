from nicegui import ui, app
from models import UserRole
from logo import logo_base64

def logout():
    """Cierra la sesión del usuario y lo redirige a la página de inicio."""
    app.storage.user.clear()
    ui.navigate.to('/')

def create_main_layout():
    """Crea la interfaz principal de la aplicación, incluyendo la cabecera y el menú lateral."""
    
    # Estilo general de la página para un fondo consistente
    ui.query('body').classes('bg-slate-100')

    # Cabecera moderna y limpia
    with ui.header(elevated=True).classes('bg-white text-gray-800 shadow-md px-4'):
        with ui.row().classes('w-full items-center justify-between'):
            # Lado izquierdo: Botón de menú y título
            with ui.row().classes('items-center gap-2'):
                ui.button(icon='menu', on_click=lambda: left_drawer.toggle()).props('flat round text-gray-600')
                ui.icon('settings', color='primary').classes('text-2xl')
                ui.label('Gestor de Soporte HelpdeskOI').classes('text-xl font-bold')

            # Lado derecho: Menú de usuario
            with ui.row().classes('items-center gap-4'):
                with ui.button(icon='person', color='primary').props('flat round'):
                    with ui.menu().classes('bg-white shadow-lg rounded-lg') as menu:
                        with ui.column().classes('p-2'):
                            ui.label(f"Usuario: {app.storage.user.get('username')}").classes('text-gray-700 font-semibold')
                            ui.label(f"Rol: {app.storage.user.get('role')}").classes('text-gray-500 text-sm')
                        ui.separator().classes('my-1')
                        ui.menu_item('Cerrar Sesión', on_click=logout, auto_close=True)

    # Menú lateral oscuro y funcional
    with ui.left_drawer().classes('bg-gray-800 text-white') as left_drawer:
        with ui.column().classes('w-full h-full justify-between no-wrap'):
            # Sección superior del menú (links)
            with ui.column().classes('w-full p-2 gap-1'):
                ui.label('Menú').classes('text-lg font-semibold p-2')
                
                # Función auxiliar para crear items de menú
                def create_menu_item(text, path, icon):
                    with ui.item().props('clickable').classes('rounded-md hover:bg-gray-700 w-full').on('click', lambda: ui.navigate.to(path)):
                        with ui.row().classes('w-full items-center gap-3 p-2'):
                            ui.icon(icon, color='white')
                            ui.label(text)

                # Link al Dashboard
                if app.storage.user.get('role') != UserRole.AUTOSERVICIO.value:
                    create_menu_item('Dashboard', '/dashboard', 'dashboard')
                
                if app.storage.user.get('role') in [UserRole.ADMINISTRADOR.value, UserRole.SUPERVISOR.value, UserRole.MONITOR.value, UserRole.TECNICO.value]:
                    create_menu_item('Búsqueda', '/search', 'search')

                # Links de Análisis (visibles para roles con permisos)
                if app.storage.user.get('role') in [UserRole.ADMINISTRADOR.value, UserRole.SUPERVISOR.value, UserRole.MONITOR.value]:
                    ui.separator().classes('bg-gray-700 my-2')
                    ui.label('Análisis').classes('text-xs text-gray-400 font-bold uppercase p-2')
                    create_menu_item('Reportes', '/reports', 'analytics')

                # Links de Administración (visibles solo para el rol 'administrador')
                if app.storage.user.get('role') == UserRole.ADMINISTRADOR.value:
                    ui.separator().classes('bg-gray-700 my-2')
                    ui.label('Administración').classes('text-xs text-gray-400 font-bold uppercase p-2')
                    
                    admin_links = {
                        'Usuarios': ('/admin/users', 'group'),
                        'Ubicaciones': ('/admin/locations', 'location_on'),
                        'Tipos de Problema': ('/admin/itil_categories', 'extension'),
                        'SLAs': ('/admin/slas', 'timer'),
                        'Config. Correo': ('/admin/mail_settings', 'mail'),
                    }
                    
                    for text, (path, icon) in admin_links.items():
                        create_menu_item(text, path, icon)

            # Sección inferior del menú (logo)
            with ui.column().classes('w-full items-center p-4'):
                ui.separator().classes('bg-gray-700 w-full mb-4')
                # Como el logo es blanco con fondo oscuro, sí será visible.
                ui.image(logo_base64).classes('w-32 opacity-30')