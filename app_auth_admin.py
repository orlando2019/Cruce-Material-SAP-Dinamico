import streamlit as st
import time
import hashlib
import json
import os
from datetime import datetime

# Configuración de la página (DEBE ser la primera instrucción de Streamlit)
st.set_page_config(
    layout="wide", page_title="Cruce de Material SAP Dinámico", page_icon="🧊"
)


# Clase para manejar la autenticación y gestión de usuarios
class UserAuth:
    def __init__(self):
        # Ruta al archivo de usuarios
        self.users_file = "users.json"
        # Configuración de tiempo de inactividad (5 minutos = 300 segundos)
        self.session_timeout = 300

        # Inicializar el tiempo de la última actividad si no existe
        if "last_activity_time" not in st.session_state:
            st.session_state.last_activity_time = time.time()

        # Crear archivo de usuarios si no existe
        if not os.path.exists(self.users_file):
            # Crear un usuario administrador por defecto
            admin_user = {
                "admin": {
                    "password": self._hash_password("admin"),
                    "email": "admin@example.com",
                    "name": "Administrador",
                    "role": "admin",
                    "enabled": True,
                    "created_at": datetime.now().isoformat(),
                    "last_login": None,
                }
            }
            with open(self.users_file, "w") as f:
                json.dump(admin_user, f, indent=4)

    def _hash_password(self, password):
        """Genera un hash seguro para la contraseña"""
        return hashlib.sha256(password.encode()).hexdigest()

    def register_user(
        self, username, password, email="", name="", role="user", enabled=True
    ):
        """Registra un nuevo usuario en el sistema"""
        # Cargar usuarios existentes
        users = self._load_users()

        # Verificar si el usuario ya existe
        if username in users:
            return False, "El nombre de usuario ya está en uso"

        # Crear nuevo usuario
        users[username] = {
            "password": self._hash_password(password),
            "email": email,
            "name": name,
            "role": role,
            "enabled": enabled,
            "created_at": datetime.now().isoformat(),
            "last_login": None,
        }

        # Guardar usuarios
        self._save_users(users)
        return True, "Usuario registrado correctamente"

    def login(self, username, password):
        """Inicia sesión con usuario y contraseña"""
        # Cargar usuarios
        users = self._load_users()

        # Verificar si el usuario existe
        if username not in users:
            return False, "Usuario no encontrado"

        # Verificar contraseña (compatible con texto plano o hash)
        stored_password = users[username]["password"]
        hashed_password = self._hash_password(password)

        # Verificar si la contraseña coincide (ya sea hasheada o en texto plano)
        if stored_password != hashed_password and stored_password != password:
            return False, "Contraseña incorrecta"

        # Si la contraseña está en texto plano, actualizarla a hash
        if stored_password == password and password != hashed_password:
            users[username]["password"] = hashed_password
            self._save_users(users)

        # Verificar si el usuario está habilitado
        if not users[username].get("enabled", True):
            return False, "Usuario deshabilitado. Contacte al administrador."

        # Asegurar que el usuario tenga un rol (para compatibilidad con datos existentes)
        if "role" not in users[username]:
            # Asignar rol de admin al usuario 'admin', usuario normal a los demás
            users[username]["role"] = "admin" if username == "admin" else "user"
            self._save_users(users)

        # Actualizar último login
        users[username]["last_login"] = datetime.now().isoformat()
        self._save_users(users)

        # Guardar información en session_state
        st.session_state["authenticated"] = True
        st.session_state["auth_time"] = time.time()
        st.session_state["username"] = username
        st.session_state["email"] = users[username]["email"]
        st.session_state["name"] = users[username]["name"]
        st.session_state["role"] = users[username].get("role", "user")

        return True, "Inicio de sesión exitoso"

    def is_authenticated(self):
        """Verifica si el usuario ya está autenticado"""
        # Verificación directa
        if not st.session_state.get("authenticated", False):
            return False

        # Verificar expiración de sesión
        current_time = time.time()
        auth_time = st.session_state.get("auth_time", 0)

        # Si ha pasado más tiempo que el límite, cerrar la sesión
        if current_time - auth_time > self.session_timeout:
            self.logout()
            return False

        # Actualizar tiempo de actividad
        st.session_state["auth_time"] = current_time
        return True

    def is_admin(self):
        """Verifica si el usuario autenticado es administrador"""
        if not self.is_authenticated():
            return False
        return st.session_state.get("role", "") == "admin"

    def logout(self):
        """Cierra la sesión del usuario"""
        # Lista de claves a eliminar
        session_keys = [
            "username",
            "email",
            "name",
            "authenticated",
            "last_activity_time",
            "auth_time",
            "role",
        ]

        # Eliminar todas las claves relacionadas con la sesión
        for key in list(st.session_state.keys()):
            if key in session_keys:
                try:
                    del st.session_state[key]
                except Exception:
                    pass

        # Crear una bandera para indicar que se ha cerrado la sesión
        st.session_state["logged_out"] = True

        # Reiniciar la página
        st.rerun()

    def get_all_users(self):
        """Obtiene todos los usuarios registrados"""
        return self._load_users()

    def update_user(self, username, data):
        """Actualiza la información de un usuario"""
        users = self._load_users()

        if username not in users:
            return False, "Usuario no encontrado"

        # Actualizar los campos proporcionados
        for key, value in data.items():
            # No actualizar la contraseña directamente
            if key != "password":
                users[username][key] = value

        self._save_users(users)
        return True, "Usuario actualizado correctamente"

    def change_password(self, username, new_password):
        """Cambia la contraseña de un usuario"""
        users = self._load_users()

        if username not in users:
            return False, "Usuario no encontrado"

        users[username]["password"] = self._hash_password(new_password)
        self._save_users(users)
        return True, "Contraseña actualizada correctamente"

    def _load_users(self):
        """Carga los usuarios desde el archivo"""
        try:
            with open(self.users_file, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_users(self, users):
        """Guarda los usuarios en el archivo"""
        with open(self.users_file, "w") as f:
            json.dump(users, f, indent=4)


# Función para mostrar la página de inicio de sesión
def login_page():
    """Muestra una página de inicio de sesión atractiva"""

    # Inicializar el autenticador
    auth = UserAuth()

    # Si ya está autenticado, no mostrar login
    if auth.is_authenticated():
        return True

    # Mostrar página de login
    col1, col2, col3, col4, col5 = st.columns([1, 1, 2, 1, 1])

    with col3:
        # Título y logo
        st.markdown(
            "<h1 style='text-align: center;'>📊 Sistema Cruce de Material SAP Dinámico</h1>",
            unsafe_allow_html=True,
        )

        # Imagen centrada
        _, col_img, _ = st.columns([2, 1, 2])
        with col_img:
            st.image("img/logo_salo.png", width=200)

        # Descripción
        st.markdown(
            "<p style='text-align: center; padding: 20px;'>Inicie sesión para acceder al sistema.</p>",
            unsafe_allow_html=True,
        )

        # Estilos CSS
        st.markdown(
            """
        <style>
        div.stButton > button {
            background-color: #4285f4;
            color: white;
            border: none;
            border-radius: 10px;
            padding: 10px 20px;
            font-size: 18px;
            font-weight: 500;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            transition: background-color 0.3s;
        }
        div.stButton > button:hover {
            background-color: #357ae8;
        }
        .auth-form {
            background-color: #f9f9f9;
            padding: 20px;
            border-radius: 10px;
            margin-top: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        </style>
        """,
            unsafe_allow_html=True,
        )

        # Formulario de inicio de sesión
        st.markdown("<div class='auth-form'>", unsafe_allow_html=True)
        username = st.text_input("Usuario", key="login_username")
        password = st.text_input("Contraseña", type="password", key="login_password")

        if st.button("Iniciar Sesión", key="btn_login"):
            if username and password:
                success, message = auth.login(username, password)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.warning("Por favor ingresa usuario y contraseña")
        st.markdown("</div>", unsafe_allow_html=True)

        # Nota informativa
        # st.info("Usuario administrador por defecto: admin / admin")

        # Pie de página
        st.markdown(
            """<p style='text-align: center; margin-top: 40px; color: #888;'>© 2025 - 
                Sistema Cruce SAP - Orland Ospino H.</p>""",
            unsafe_allow_html=True,
        )

    # Prevenir que se muestre el resto de la app
    st.stop()
    return False


# Función para verificar la autenticación
def check_auth():
    """Verifica la autenticación y muestra la página de login si es necesario"""
    auth = UserAuth()

    # Verificar si está autenticado
    if auth.is_authenticated():
        return True

    # Si no está autenticado, mostrar página de login
    login_page()
    return False


# Función para mostrar el botón de cierre de sesión
def get_logout_button():
    """Devuelve un botón de cierre de sesión que puede usarse en la UI principal"""
    auth = UserAuth()

    if st.button(
        " Cerrar Sesión",
        icon="🔐",
        key="btn_logout",
        help="Cerrar Sesión",
        type="primary",
    ):
        auth.logout()


# Función para mostrar la vista de administración
def admin_view():
    """Muestra la vista de administración para gestionar usuarios"""
    auth = UserAuth()

    # Verificar si el usuario es administrador
    if not auth.is_admin():
        st.warning("No tienes permisos para acceder a esta sección")
        st.stop()

    st.title("Panel de Administración")
    st.subheader("Gestión de Usuarios")

    # Tabs para las diferentes secciones
    tab1, tab2 = st.tabs(["Registrar Usuario", "Gestionar Usuarios"])

    # Tab para registrar nuevos usuarios
    with tab1:
        st.subheader("Registrar Nuevo Usuario")

        # Formulario de registro
        with st.form("register_form"):
            new_username = st.text_input("Usuario")
            new_password = st.text_input("Contraseña", type="password")
            confirm_password = st.text_input("Confirmar Contraseña", type="password")
            email = st.text_input("Correo Electrónico (opcional)")
            name = st.text_input("Nombre Completo")
            role = st.selectbox("Rol", options=["user", "admin"])
            enabled = st.checkbox("Usuario Habilitado", value=True)

            submit = st.form_submit_button("Registrar Usuario")

            if submit:
                if not new_username or not new_password:
                    st.warning("Usuario y contraseña son obligatorios")
                elif new_password != confirm_password:
                    st.error("Las contraseñas no coinciden")
                else:
                    success, message = auth.register_user(
                        new_username, new_password, email, name, role, enabled
                    )
                    if success:
                        st.success(message)
                    else:
                        st.error(message)

    # Tab para gestionar usuarios existentes
    with tab2:
        st.subheader("Lista de Usuarios")

        # Obtener todos los usuarios
        users = auth.get_all_users()

        if not users:
            st.info("No hay usuarios registrados")
        else:
            # Crear una tabla para mostrar los usuarios
            user_data = []
            for username, data in users.items():
                user_data.append(
                    {
                        "Usuario": username,
                        "Nombre": data.get("name", ""),
                        "Email": data.get("email", ""),
                        "Rol": data.get("role", "user"),
                        "Habilitado": data.get("enabled", True),
                        "Último Login": data.get("last_login", "Nunca"),
                    }
                )

            # Mostrar la tabla de usuarios con más detalles
            user_table = []
            for username, data in users.items():
                # Formatear la fecha de creación para mejor legibilidad
                created_at = data.get("created_at", "Desconocido")
                if created_at != "Desconocido":
                    try:
                        created_date = datetime.fromisoformat(created_at)
                        created_at = created_date.strftime("%d/%m/%Y %H:%M")
                    except Exception:
                        pass  # Mantener el formato original si hay error

                # Formatear la fecha de último login
                last_login = data.get("last_login", "Nunca")
                if last_login != "Nunca":
                    try:
                        login_date = datetime.fromisoformat(last_login)
                        last_login = login_date.strftime("%d/%m/%Y %H:%M")
                    except Exception:
                        pass  # Mantener el formato original si hay error

                user_table.append(
                    {
                        "Usuario": username,
                        "Nombre": data.get("name", ""),
                        "Email": data.get("email", ""),
                        "Rol": data.get("role", "user"),
                        "Habilitado": "Sí" if data.get("enabled", True) else "No",
                        "Creado": created_at,
                        "Último Acceso": last_login,
                    }
                )

            st.dataframe(user_table, use_container_width=True)

            # Sección para editar usuarios
            st.subheader("Editar Usuario")

            # Seleccionar usuario a editar
            user_to_edit = st.selectbox(
                "Seleccionar Usuario", options=list(users.keys())
            )

            if user_to_edit:
                user_data = users[user_to_edit]

                # Mostrar fecha de creación
                created_at = user_data.get("created_at", "Desconocido")
                if created_at != "Desconocido":
                    try:
                        created_date = datetime.fromisoformat(created_at)
                        created_at = created_date.strftime("%d/%m/%Y %H:%M")
                    except Exception:
                        pass

                st.info(f"Creado: {created_at}")

            # Formulario para editar usuario
            if user_to_edit:
                with st.form("edit_user_form"):
                    new_username = st.text_input(
                        "Nombre de Usuario", value=user_to_edit
                    )
                    edit_name = st.text_input(
                        "Nombre Completo", value=user_data.get("name", "")
                    )
                    edit_email = st.text_input(
                        "Email", value=user_data.get("email", "")
                    )
                    edit_role = st.selectbox(
                        "Rol",
                        options=["user", "admin"],
                        index=0 if user_data.get("role", "") == "user" else 1,
                    )
                    edit_enabled = st.checkbox(
                        "Usuario Habilitado", value=user_data.get("enabled", True)
                    )
                    change_pwd = st.checkbox("Cambiar Contraseña")
                    new_pwd = st.text_input(
                        "Nueva Contraseña", type="password", disabled=not change_pwd
                    )

                    submit_edit = st.form_submit_button("Guardar Cambios")

                    if submit_edit:
                        # Verificar si se cambió el nombre de usuario
                        username_changed = new_username != user_to_edit

                        if username_changed and new_username in users:
                            st.error(
                                f"El nombre de usuario '{new_username}' ya existe. Elija otro."
                            )
                        else:
                            # Actualizar información del usuario
                            update_data = {
                                "name": edit_name,
                                "email": edit_email,
                                "role": edit_role,
                                "enabled": edit_enabled,
                            }

                            # Si se cambió el nombre de usuario, crear uno nuevo y eliminar el viejo
                            if username_changed:
                                # Copiar todos los datos del usuario actual
                                new_user_data = users[user_to_edit].copy()
                                # Actualizar con los nuevos datos
                                new_user_data.update(update_data)
                                # Crear el nuevo usuario
                                users[new_username] = new_user_data
                                # Eliminar el usuario antiguo
                                del users[user_to_edit]
                                # Guardar cambios
                                auth._save_users(users)
                                success, message = (
                                    True,
                                    f"Usuario actualizado de '{user_to_edit}' a '{new_username}'",
                                )
                            else:
                                # Actualizar el usuario existente
                                success, message = auth.update_user(
                                    user_to_edit, update_data
                                )

                            # Si se solicitó cambio de contraseña
                            if change_pwd and new_pwd:
                                # Usar el nuevo nombre de usuario si cambió
                                target_user = (
                                    new_username if username_changed else user_to_edit
                                )
                                pwd_success, pwd_message = auth.change_password(
                                    target_user, new_pwd
                                )
                                if pwd_success:
                                    st.success(pwd_message)
                                else:
                                    st.error(pwd_message)

                            if success:
                                st.success(message)
                                # Limpiar el formulario y actualizar la página
                                st.rerun()
                            else:
                                st.error(message)


# Función para mostrar la aplicación principal
def main_app():
    """Muestra la aplicación principal - Cruce de Material SAP Dinámico"""
    import streamlit as st
    from cruce_sap import (
        cruce_material_sap_procesado_con_split,
        to_excel_bytes,
        limpiar_estado,
    )
    import pandas as pd

    # Encabezado y botones de la interfaz
    col_titulo, col_usuario = st.columns([4, 1])

    with col_titulo:
        st.title("📊 Aplicación de Cruce de Material SAP Dinámico")

    with col_usuario:
        # Mostrar información del usuario autenticado
        if "email" in st.session_state and st.session_state.email:
            st.write(f"👤 **Usuario:** {st.session_state.email}")

    # Inicializar variables de session_state necesarias
    if "uploaded_file_obj" not in st.session_state:
        st.session_state.uploaded_file_obj = None
    if "sheet_names" not in st.session_state:
        st.session_state.sheet_names = []
    if "df_desc_cols" not in st.session_state:
        st.session_state.df_desc_cols = []
    if "df_exist_cols" not in st.session_state:
        st.session_state.df_exist_cols = []
    if "df_result" not in st.session_state:
        st.session_state.df_result = None
    if "processed_successfully" not in st.session_state:
        st.session_state.processed_successfully = False

    # Botón para limpiar estado
    if st.button(
        "Limpiar Todo",
        icon="🗑️",
        key="btn_limpiar",
        help="Limpiar Todo",
        type="secondary",
    ):
        limpiar_estado()
        st.rerun()

    st.markdown("""
    Sube tu archivo Excel, selecciona las hojas y mapea las columnas.
    La aplicación ajustará el stock SAP progresivamente y dividirá las planillas si el stock es insuficiente.
    """)

    # --- IMPORTACIÓN Y PROCESAMIENTO DE ARCHIVOS ---
    from cruce_sap import EXPECTED_COLS_DESC, EXPECTED_COLS_EXIST

    uploaded_file = st.file_uploader(
        "Carga tu archivo Excel",
        type=["xlsx", "xls"],
        key="file_uploader_widget_split",
    )

    if uploaded_file:
        if (
            st.session_state.uploaded_file_obj is None
            or uploaded_file.name != st.session_state.uploaded_file_obj.name
        ):
            st.session_state.uploaded_file_obj = uploaded_file
            st.session_state.sheet_names = []
            st.session_state.df_desc_cols = []
            st.session_state.df_exist_cols = []
            st.session_state.df_result = None
            st.session_state.processed_successfully = False
            for key_map in list(st.session_state.keys()):
                if key_map.startswith("map_desc_") or key_map.startswith("map_exist_"):
                    del st.session_state[key_map]
            if "prev_sheet_desc" in st.session_state:
                del st.session_state.prev_sheet_desc
            if "prev_sheet_exist" in st.session_state:
                del st.session_state.prev_sheet_exist
            st.rerun()

        try:
            if not st.session_state.sheet_names:
                xls = pd.ExcelFile(st.session_state.uploaded_file_obj)
                st.session_state.sheet_names = xls.sheet_names
        except Exception as e:
            st.error(f"Error al leer el archivo Excel: {e}")
            st.session_state.uploaded_file_obj = None
            return

        st.sidebar.header("1. Selección de Hojas")
        default_idx_desc = 0
        if st.session_state.sheet_names:
            try:
                default_idx_desc = [
                    s.lower() for s in st.session_state.sheet_names
                ].index("material por descargar")
            except ValueError:
                default_idx_desc = 0

        selected_sheet_desc = st.sidebar.selectbox(
            "Hoja 'Material por Descargar'",
            st.session_state.sheet_names,
            index=default_idx_desc,
            key="sel_sheet_desc",
        )

        default_idx_exist = 0
        if st.session_state.sheet_names:
            try:
                default_idx_exist = [
                    s.lower() for s in st.session_state.sheet_names
                ].index("existencia")
            except ValueError:
                default_idx_exist = 1 if len(st.session_state.sheet_names) > 1 else 0
        selected_sheet_exist = st.sidebar.selectbox(
            "Hoja 'Existencia SAP'",
            st.session_state.sheet_names,
            index=default_idx_exist,
            key="sel_sheet_exist",
        )

        try:
            if selected_sheet_desc and (
                not st.session_state.df_desc_cols
                or st.session_state.get("prev_sheet_desc") != selected_sheet_desc
            ):
                df_temp_desc = pd.read_excel(
                    st.session_state.uploaded_file_obj,
                    sheet_name=selected_sheet_desc,
                    dtype=str,
                )
                st.session_state.df_desc_cols = [""] + df_temp_desc.columns.tolist()
                st.session_state.prev_sheet_desc = selected_sheet_desc

            if selected_sheet_exist and (
                not st.session_state.df_exist_cols
                or st.session_state.get("prev_sheet_exist") != selected_sheet_exist
            ):
                df_temp_exist = pd.read_excel(
                    st.session_state.uploaded_file_obj,
                    sheet_name=selected_sheet_exist,
                    dtype=str,
                )
                st.session_state.df_exist_cols = [""] + df_temp_exist.columns.tolist()
                st.session_state.prev_sheet_exist = selected_sheet_exist
        except Exception as e:
            st.error(f"Error al leer las columnas de las hojas: {e}")
            return

        st.sidebar.header("2. Mapeo de Columnas")
        user_mappings_desc = {}
        user_mappings_exist = {}

        st.sidebar.markdown("**Hoja 'Material por Descargar':**")
        for key_internal, expected_col_name_std in EXPECTED_COLS_DESC.items():
            default_index = 0
            if st.session_state.df_desc_cols:
                try:
                    default_index = st.session_state.df_desc_cols.index(
                        expected_col_name_std
                    )
                except ValueError:
                    try:
                        default_index = [
                            c.lower() for c in st.session_state.df_desc_cols
                        ].index(expected_col_name_std.lower())
                    except ValueError:
                        original_common_name = ""
                        if key_internal == "item_id_desc":
                            original_common_name = "Item"
                        elif key_internal == "material_code":
                            original_common_name = "MATERIAL"
                        elif key_internal == "description_desc":
                            # Para descripcion buscamos primero Texto breve de
                            # material si existe
                            try:
                                if (
                                    "Texto breve de material"
                                    in st.session_state.df_desc_cols
                                ):
                                    original_common_name = "Texto breve de material"
                                else:
                                    original_common_name = "Descripción"
                            except Exception:
                                original_common_name = "Descripción"
                        elif key_internal == "codigo_obra_sgt":
                            # Para codigo de obra buscamos varias opciones
                            # comunes
                            try:
                                if "CODIGO OBRA SGT" in st.session_state.df_desc_cols:
                                    original_common_name = "CODIGO OBRA SGT"
                                elif "CODIGO OBRA" in st.session_state.df_desc_cols:
                                    original_common_name = "CODIGO OBRA"
                                elif "Descripción" in st.session_state.df_desc_cols:
                                    original_common_name = "Descripción"
                                else:
                                    original_common_name = ""
                            except Exception:
                                original_common_name = ""
                        elif key_internal == "planilla_name":
                            original_common_name = "NOMBRE PLANILLA"
                        elif key_internal == "quantity_planilla":
                            original_common_name = "Cantidad"
                        if original_common_name:
                            try:
                                default_index = st.session_state.df_desc_cols.index(
                                    original_common_name
                                )
                            except ValueError:
                                try:
                                    default_index = [
                                        c.lower() for c in st.session_state.df_desc_cols
                                    ].index(original_common_name.lower())
                                except ValueError:
                                    default_index = 0
                        else:
                            default_index = 0
            # Usar colecciones estándar sin agregar columnas falsas que puedan
            # causar problemas
            user_col_selection = st.sidebar.selectbox(
                f"{expected_col_name_std} (Descarga):",
                st.session_state.df_desc_cols,
                index=default_index,
                key=f"map_desc_{key_internal}",
            )
            if user_col_selection:
                user_mappings_desc[expected_col_name_std] = user_col_selection

        st.sidebar.markdown("**Hoja 'Existencia SAP':**")
        for key_internal, expected_col_name_std in EXPECTED_COLS_EXIST.items():
            default_index = 0
            if st.session_state.df_exist_cols:
                try:
                    default_index = st.session_state.df_exist_cols.index(
                        expected_col_name_std
                    )
                except ValueError:
                    try:
                        default_index = [
                            c.lower() for c in st.session_state.df_exist_cols
                        ].index(expected_col_name_std.lower())
                    except ValueError:
                        original_common_name = ""
                        if key_internal == "item_id_exist":
                            original_common_name = "Item"  # O 'ITEM'
                        elif key_internal == "description_exist":
                            original_common_name = "Texto breve de material"
                        elif key_internal == "stock_sap_qty":
                            original_common_name = "Libre utilización"
                        if original_common_name:
                            try:
                                default_index = st.session_state.df_exist_cols.index(
                                    original_common_name
                                )
                            except ValueError:
                                try:
                                    default_index = [
                                        c.lower()
                                        for c in st.session_state.df_exist_cols
                                    ].index(original_common_name.lower())
                                except ValueError:
                                    default_index = 0
                        else:
                            default_index = 0
            user_col_selection = st.sidebar.selectbox(
                f"{expected_col_name_std} (Existencia):",
                st.session_state.df_exist_cols,
                index=default_index,
                key=f"map_exist_{key_internal}",
            )
            if user_col_selection:
                user_mappings_exist[expected_col_name_std] = user_col_selection

        all_desc_mapped = len(user_mappings_desc) == len(EXPECTED_COLS_DESC)
        all_exist_mapped = len(user_mappings_exist) == len(EXPECTED_COLS_EXIST)
        if not all_desc_mapped:
            st.sidebar.warning(
                "Mapea todas las columnas para 'Material por Descargar'."
            )
        if not all_exist_mapped:
            st.sidebar.warning("Mapea todas las columnas para 'Existencia SAP'.")

        if st.button(
            "🚀 Procesar Cruce (con Split)",
            type="primary",
            key="process_button_split_key",
            disabled=not (all_desc_mapped and all_exist_mapped),
        ):
            st.session_state.processed_successfully = False
            st.session_state.df_result = None
            with st.spinner("Procesando con división de líneas..."):
                try:
                    df_desc_original = pd.read_excel(
                        st.session_state.uploaded_file_obj,
                        sheet_name=selected_sheet_desc,
                        dtype=str,
                    )
                    df_exist_original = pd.read_excel(
                        st.session_state.uploaded_file_obj,
                        sheet_name=selected_sheet_exist,
                        dtype=str,
                    )

                    df_desc_std = pd.DataFrame()
                    for expected_name_std, user_col_name in user_mappings_desc.items():
                        # Manejar el caso especial cuando se selecciona 'Texto breve de material'
                        # pero esa columna no existe en los datos originales
                        if (
                            user_col_name == "Texto breve de material"
                            and user_col_name not in df_desc_original.columns
                        ):
                            # Si no existe, usamos una columna vacía
                            df_desc_std[expected_name_std] = ""
                        else:
                            df_desc_std[expected_name_std] = df_desc_original[
                                user_col_name
                            ]

                    df_exist_std = pd.DataFrame()
                    for expected_name_std, user_col_name in user_mappings_exist.items():
                        df_exist_std[expected_name_std] = df_exist_original[
                            user_col_name
                        ]

                    # *** LLAMADA A LA NUEVA LÓGICA ***
                    st.session_state.df_result = cruce_material_sap_procesado_con_split(
                        df_desc_std, df_exist_std
                    )

                    if st.session_state.df_result is not None:
                        st.session_state.processed_successfully = True
                    else:
                        st.error(
                            "El procesamiento (con split) falló o no generó un DataFrame."
                        )
                except Exception as e:
                    st.error(f"Error crítico durante el procesamiento (con split): {e}")
                    import traceback

                    st.error(traceback.format_exc())
                    st.session_state.df_result = None
                    st.session_state.processed_successfully = False

    # --- Mostrar resultados ---
    if (
        st.session_state.processed_successfully
        and st.session_state.df_result is not None
    ):
        if not st.session_state.df_result.empty:
            st.success("✅ ¡Proceso con división de líneas completado!")
            st.subheader("📋 Vista Previa del Resultado")
            # Mostrar más filas por si hay splits
            st.dataframe(st.session_state.df_result.head(30))

            st.subheader("📊 Resumen del Resultado")
            col_res1, col_res2, col_res3 = st.columns(3)
            col_res1.metric("Total de Filas Generadas", len(st.session_state.df_result))
            if "Diferencia" in st.session_state.df_result.columns:
                sum_diferencia = pd.to_numeric(
                    st.session_state.df_result["Diferencia"], errors="coerce"
                ).sum()
                col_res2.metric("Suma Total de 'Diferencia'", f"{sum_diferencia:,.0f}")
            if "Descargable" in st.session_state.df_result.columns:
                desc_si_count = (
                    st.session_state.df_result["Descargable"] == "Si"
                ).sum()
                desc_no_count = (  # noqa: F841
                    st.session_state.df_result["Descargable"] == "No"
                ).sum()
                col_res3.metric("Descargable 'Sí'", desc_si_count)
                # Podríamos añadir otra métrica para 'No' si es relevante

            excel_bytes = to_excel_bytes(st.session_state.df_result)
            st.download_button(
                label="📥 Descargar Resultado (con Split) como Excel",
                data=excel_bytes,
                file_name="Cruce_Material_SAP_Split_Streamlit.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_button_split_key",
            )
        else:
            st.warning(
                "⚠️ El proceso se completó, pero el DataFrame resultante está vacío. Revisa datos y mapeos."
            )
            st.dataframe(st.session_state.df_result)
    elif (
        st.session_state.uploaded_file_obj
        and not st.session_state.processed_successfully
        and st.session_state.df_result is None
        and st.session_state.get("process_button_split_key")
    ):
        st.error(
            "❌ El procesamiento (con split) no pudo completarse. Revisa mensajes."
        )
    if not st.session_state.uploaded_file_obj:
        st.info("Por favor, carga un archivo Excel.")

    st.markdown("---")


# Función principal que controla la navegación y flujo de la aplicación
def main():
    """Función principal que controla la navegación y flujo de la aplicación"""
    # Inicializar el autenticador
    auth = UserAuth()

    # Verificar autenticación
    if not check_auth():
        return

    # Configurar la barra lateral para navegación
    with st.sidebar:
        st.title("Navegación")

        # Mostrar nombre del usuario
        st.write(f"Usuario: **{st.session_state.get('name', 'Usuario')}**")

        # Opciones de navegación
        app_options = ["Aplicación Principal"]

        # Añadir opción de administración solo para administradores
        if auth.is_admin():
            app_options.insert(0, "Registrar Usuario / Gestión Admin")

        # Selector de navegación
        navigation = st.radio("Ir a:", app_options)

        # Botón de cierre de sesión
        get_logout_button()

    # Mostrar la vista correspondiente según la navegación
    if navigation == "Registrar Usuario / Gestión Admin":
        admin_view()
    else:  # Aplicación Principal
        main_app()


# Ejecutar la aplicación
if __name__ == "__main__":
    main()
