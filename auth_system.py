import streamlit as st
import time
import hashlib
import json
import os
from datetime import datetime

# Clase para manejar la autenticación con usuario y contraseña
class UserAuth:
    def __init__(self):
        # Ruta al archivo de usuarios
        self.users_file = "users.json"
        # Configuración de tiempo de inactividad (5 minutos = 300 segundos)
        self.session_timeout = 300
        
        # Inicializar el tiempo de la última actividad si no existe
        if 'last_activity_time' not in st.session_state:
            st.session_state.last_activity_time = time.time()
        
        # Crear archivo de usuarios si no existe
        if not os.path.exists(self.users_file):
            with open(self.users_file, "w") as f:
                json.dump({}, f)
    
    def _hash_password(self, password):
        """Genera un hash seguro para la contraseña"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def register_user(self, username, password, email="", name=""):
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
            "created_at": datetime.now().isoformat(),
            "last_login": None
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
        
        # Verificar contraseña
        if users[username]["password"] != self._hash_password(password):
            return False, "Contraseña incorrecta"
        
        # Actualizar último login
        users[username]["last_login"] = datetime.now().isoformat()
        self._save_users(users)
        
        # Guardar información en session_state
        st.session_state["authenticated"] = True
        st.session_state["auth_time"] = time.time()
        st.session_state["username"] = username
        st.session_state["email"] = users[username]["email"]
        st.session_state["name"] = users[username]["name"]
        st.session_state["auth_method"] = "password"
        
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
    
    def logout(self):
        """Cierra la sesión del usuario"""
        # Lista de claves a eliminar
        session_keys = ['username', 'email', 'name', 'authenticated', 'last_activity_time', 'auth_time', 'auth_method']
        
        # Eliminar todas las claves relacionadas con la sesión
        for key in list(st.session_state.keys()):
            if key in session_keys:
                try:
                    del st.session_state[key]
                except:
                    pass
        
        # Crear una bandera para indicar que se ha cerrado la sesión
        st.session_state['logged_out'] = True
        
        # Reiniciar la página
        st.rerun()
    
    def _load_users(self):
        """Carga los usuarios desde el archivo"""
        try:
            with open(self.users_file, "r") as f:
                return json.load(f)
        except:
            return {}
    
    def _save_users(self, users):
        """Guarda los usuarios en el archivo"""
        with open(self.users_file, "w") as f:
            json.dump(users, f, indent=4)

# Funciones para usar en la aplicación principal
def login_page():
    """Muestra una página de inicio de sesión atractiva"""
    # Inicializar el autenticador
    auth = UserAuth()
    
    # Si ya está autenticado, no mostrar login
    if auth.is_authenticated():
        return True
    
    # Mostrar página de login
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Título y logo
        st.markdown("<h1 style='text-align: center;'>Sistema de Cruce de Material SAP</h1>", unsafe_allow_html=True)
        
        # Imagen centrada
        _, col_img, _ = st.columns([2, 1, 2])
        with col_img:
            st.image("img/logo_salo.png", width=250)
        
        # Descripción
        st.markdown("<p style='text-align: center; padding: 20px;'>Esta aplicación te permite realizar cruces de material SAP de forma eficiente, ajustando el stock progresivamente.</p>", unsafe_allow_html=True)
        
        # Estilos CSS
        st.markdown("""
        <style>
        div.stButton > button {
            background-color: #4285f4;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 10px 20px;
            font-size: 16px;
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
            border-radius: 8px;
            margin-top: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Tabs para login y registro
        tab1, tab2 = st.tabs(["Iniciar Sesión", "Registrarse"])
        
        # Tab de inicio de sesión
        with tab1:
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
        
        # Tab de registro
        with tab2:
            st.markdown("<div class='auth-form'>", unsafe_allow_html=True)
            new_username = st.text_input("Usuario", key="reg_username")
            new_password = st.text_input("Contraseña", type="password", key="reg_password")
            confirm_password = st.text_input("Confirmar Contraseña", type="password", key="reg_confirm")
            email = st.text_input("Correo Electrónico (opcional)", key="reg_email")
            name = st.text_input("Nombre Completo (opcional)", key="reg_name")
            
            if st.button("Registrarse", key="btn_register"):
                if not new_username or not new_password:
                    st.warning("Usuario y contraseña son obligatorios")
                elif new_password != confirm_password:
                    st.error("Las contraseñas no coinciden")
                else:
                    success, message = auth.register_user(new_username, new_password, email, name)
                    if success:
                        st.success(message)
                        # Iniciar sesión automáticamente
                        auth.login(new_username, new_password)
                        st.rerun()
                    else:
                        st.error(message)
            st.markdown("</div>", unsafe_allow_html=True)
        
        # Pie de página
        st.markdown("<p style='text-align: center; margin-top: 40px; color: #888;'>© 2025 - Sistema de Cruce SAP - Orlanndo Ospino H.</p>", unsafe_allow_html=True)
    
    # Prevenir que se muestre el resto de la app
    st.stop()
    return False

def check_auth():
    """Verifica la autenticación y muestra la página de login si es necesario"""
    auth = UserAuth()
    
    # Verificar si está autenticado
    if auth.is_authenticated():
        return True
    
    # Si no está autenticado, mostrar página de login
    login_page()
    return False

def get_logout_button():
    """Devuelve un botón de cierre de sesión que puede usarse en la UI principal"""
    auth = UserAuth()
    
    if st.button(" Cerrar Sesión", icon="🔐", key="btn_logout", help="Cerrar Sesión", type="primary"):
        auth.logout()
