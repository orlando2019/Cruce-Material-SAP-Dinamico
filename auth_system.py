import streamlit as st
import requests
import urllib.parse
import time

# Clase para manejar la autenticación con Google OAuth2
class GoogleAuth:
    def __init__(self):
        # Cargar configuraciones desde secrets.toml
        self.client_id = st.secrets.get("client_id", "")
        self.client_secret = st.secrets.get("client_secret", "")
        self.redirect_uri = st.secrets.get("redirect_url_test", "http://localhost:8501/")
        self.auth_url = f"https://accounts.google.com/o/oauth2/auth"
        self.token_url = "https://oauth2.googleapis.com/token"
        self.scope = "openid email profile"
        
        # Configuración de tiempo de inactividad (5 minutos = 300 segundos)
        self.session_timeout = 300
        
        # Inicializar el tiempo de la última actividad si no existe
        if 'last_activity_time' not in st.session_state:
            st.session_state.last_activity_time = time.time()
        
    def is_authenticated(self):
        """Verifica si el usuario ya está autenticado"""
        # Verificación más simple y directa: comprobar si la clave 'authenticated' está en session_state
        if not st.session_state.get("authenticated", False):
            return False
            
        # Verificar expiración de sesión
        current_time = time.time()
        auth_time = st.session_state.get("auth_time", 0)
        
        # Si ha pasado más tiempo que el límite, cerrar la sesión
        if current_time - auth_time > self.session_timeout:
            # Solo hacer logout si ha expirado por inactividad
            self.logout()
            return False
            
        # Si llega aquí, actualizar tiempo de actividad
        st.session_state["auth_time"] = current_time
        return True
    
    def get_login_url(self):
        """Construye la URL de inicio de sesión con Google"""
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "scope": self.scope,
            "access_type": "offline"
        }
        return f"{self.auth_url}?{urllib.parse.urlencode(params)}"
    
    def process_callback(self):
        """Procesa el callback después de la autenticación con Google"""
        # Si ya está autenticado en session_state, no hacer nada más
        if self.is_authenticated():
            return True
            
        # Obtener código de autorización desde parámetros de URL
        code = st.query_params.get("code")
        
        if code:
            # Intercambiar código por token
            token_data = self._exchange_code_for_token(code)
            
            if token_data and "access_token" in token_data:
                # Obtener información del usuario usando el token
                user_info = self._get_user_info(token_data["access_token"])
                
                if user_info and "email" in user_info:
                    # Guardar información en session_state y marcar como autenticado
                    st.session_state["authenticated"] = True  # Clave principal para verificar autenticación
                    st.session_state["auth_time"] = time.time()  # Tiempo de autenticación
                    st.session_state["access_token"] = token_data["access_token"]  # Guardar token
                    st.session_state["email"] = user_info.get("email")
                    st.session_state["name"] = user_info.get("name")
                    st.session_state["profile_pic"] = user_info.get("picture")
                    
                    # Eliminar código de la URL para evitar problemas al recargar
                    st.query_params.pop("code", None)
                    return True
        
        return False
    
    def _exchange_code_for_token(self, code):
        """Intercambia el código de autorización por un token de acceso"""
        try:
            data = {
                'code': code,
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'redirect_uri': self.redirect_uri,
                'grant_type': 'authorization_code'
            }
            
            response = requests.post(self.token_url, data=data)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            st.error(f"Error al intercambiar el código: {str(e)}")
        
        return None
    
    def _get_user_info(self, access_token):
        """Obtiene información del usuario usando el token de acceso"""
        try:
            headers = {'Authorization': f'Bearer {access_token}'}
            response = requests.get('https://www.googleapis.com/oauth2/v3/userinfo', headers=headers)
            
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            st.error(f"Error al obtener información del usuario: {str(e)}")
        
        return None
    
    def logout(self):
        """Cierra la sesión del usuario"""
        # Lista de claves a eliminar para limpiar completamente la sesión
        session_keys = ['email', 'name', 'profile_pic', 'authenticated', 'last_activity_time', 'auth_time', 'access_token']
        
        # Eliminar todas las claves relacionadas con la sesión
        for key in st.session_state.keys():
            if key in session_keys or key.startswith('_oauth_') or key.startswith('auth_'):
                try:
                    del st.session_state[key]
                except:
                    pass  # Ignorar errores si la clave no existe
                
        # Crear una bandera para indicar que se ha cerrado la sesión (evitar bucles)
        st.session_state['logged_out'] = True
        
        # Reiniciar la página para mostrar la pantalla de login
        st.rerun()

# Funciones para usar en la aplicación principal
def login_page():
    """Muestra una página de inicio de sesión atractiva"""
    # Inicializar el autenticador
    auth = GoogleAuth()
    
    # Verificar si hay un código en la URL (callback después de autenticación)
    if auth.process_callback():
        return True
    
    # Si no está autenticado, mostrar página de login
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Una sola imagen centrada y título
        st.markdown("<h1 style='text-align: center;'>Sistema de Cruce de Material SAP</h1>", unsafe_allow_html=True)
        
        # Imagen única centrada con tamaño reducido
        _, col_img, _ = st.columns([2, 1, 2])  # Columnas para centrar mejor la imagen
        with col_img:
            st.image("img/logo_salo.png", width=250)  # Reducir ancho a 120px
        
        # Breve descripción centrada
        st.markdown("<p style='text-align: center; padding: 20px;'>Esta aplicación te permite realizar cruces de material SAP de forma eficiente, ajustando el stock progresivamente.</p>", unsafe_allow_html=True)
        
        # Contenedor simple para el login
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
        </style>
        """, unsafe_allow_html=True)
        
        # URL para inicio de sesión
        login_url = auth.get_login_url()
        
        if st.button("Iniciar sesión con Google"):
            st.markdown(f'<meta http-equiv="refresh" content="0;URL=\'{login_url}\'">', unsafe_allow_html=True)
        
        # Pie de página
        st.markdown("<p style='text-align: center; margin-top: 40px; color: #888;'>© 2025 - Sistema de Cruce SAP - Orlanndo Ospino H.</p>", unsafe_allow_html=True)
    
    # Prevenir que se muestre el resto de la app
    st.stop()
    return False

def check_auth():
    """Verifica la autenticación y muestra la página de login si es necesario"""
    auth = GoogleAuth()
    
    # Si no está autenticado, mostrar página de login
    if not auth.is_authenticated():
        login_page()
        return False
    
    # Verificar callback de Google
    if auth.process_callback():
        return True
    
    return True

def get_logout_button():
    """Devuelve un botón de cierre de sesión que puede usarse en la UI principal"""
    auth = GoogleAuth()
    
    if st.button(" Cerrar Sesión",icon="🔐", key="btn_logout", help="Cerrar Sesión", type="primary"):
        auth.logout()
