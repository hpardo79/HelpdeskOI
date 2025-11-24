# Guía para subir tu proyecto a GitHub

Sigue estos pasos para instalar Git, configurar tu repositorio y subir tu código a GitHub.

## 1. Instalar Git

Como estás en Linux (Ubuntu/Debian), abre tu terminal y ejecuta:

```bash
sudo apt update
sudo apt install git
```

Verifica la instalación comprobando la versión:
```bash
git --version
```

## 2. Configuración Inicial (Solo si es tu primera vez)

Si nunca has usado Git en esta máquina, necesitas configurar tu nombre y correo (usa el mismo de tu cuenta de GitHub):

```bash
git config --global user.name "Tu Nombre"
git config --global user.email "tu_email@ejemplo.com"
```

## 3. Inicializar el Repositorio Local

Asegúrate de estar en la carpeta de tu proyecto (`/home/itsupport/Development/nicegui-dev/helpdeskoi`).

1.  **Inicializar Git:**
    ```bash
    git init
    ```
    *Esto crea una carpeta oculta `.git` donde se guarda el historial.*

2.  **Verificar archivos ignorados:**
    Ya tienes un archivo `.gitignore` configurado, así que los archivos temporales y secretos (como `.env` o la base de datos) no se subirán. Puedes verificar qué se subirá con:
    ```bash
    git status
    ```

3.  **Añadir archivos al área de preparación (Staging):**
    ```bash
    git add .
    ```
    *El punto `.` significa "todo lo que hay en este directorio".*

4.  **Hacer el primer Commit (Guardar cambios):**
    ```bash
    git commit -m "Primer commit: Versión inicial de HelpdeskOI"
    ```

## 4. Crear el Repositorio en GitHub

1.  Ve a [github.com](https://github.com) e inicia sesión.
2.  Haz clic en el botón **+** (arriba a la derecha) y selecciona **New repository**.
3.  **Repository name:** `helpdeskoi` (o el nombre que prefieras).
4.  **Description:** (Opcional) "Sistema de Helpdesk con Python y NiceGUI".
5.  **Public/Private:** Elige si quieres que sea público o privado.
6.  **IMPORTANTE:** No marques ninguna casilla de "Initialize this repository with..." (ni README, ni .gitignore, ni License), ya que vamos a subir un repositorio existente.
7.  Haz clic en **Create repository**.

## 5. Conectar y Subir (Push)

Una vez creado el repositorio, GitHub te mostrará unos comandos. Busca la sección **"…or push an existing repository from the command line"**.

Copia y ejecuta esos comandos en tu terminal. Serán parecidos a estos (asegúrate de usar TU usuario):

1.  **Renombrar la rama principal a 'main' (estándar moderno):**
    ```bash
    git branch -M main
    ```

2.  **Añadir la dirección remota (el enlace a tu GitHub):**
    ```bash
    git remote add origin https://github.com/TU_USUARIO/helpdeskoi.git
    ```
    *(Reemplaza `TU_USUARIO` con tu nombre de usuario real de GitHub)*

3.  **Subir los archivos:**
    ```bash
    git push -u origin main
    ```

    *Te pedirá tu usuario y contraseña de GitHub. **Nota:** Si tienes activada la autenticación de dos factores o usas una contraseña normal, es posible que necesites usar un "Personal Access Token" en lugar de tu contraseña.*

---

¡Listo! Si recargas la página de tu repositorio en GitHub, verás todo tu código subido.
