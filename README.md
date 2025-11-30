# 🚀 Aplicación de Cruce de Material SAP Dinámico

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)](https://streamlit.io/)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Aplicación web desarrollada con Streamlit que permite realizar el cruce de materiales con el stock SAP, ajustando el stock de forma progresiva y dividiendo las líneas cuando la cantidad solicitada excede el stock disponible. Optimiza el proceso de gestión de inventario y despacho de materiales.

## 📋 Características

- **🔐 Autenticación con Google** - Acceso seguro mediante OAuth2
- **📊 Interfaz intuitiva** - Diseño responsive y fácil de usar
- **🔄 Carga flexible** - Soporte para múltiples formatos de Excel
- **🎯 Mapeo dinámico** - Adaptación a diferentes estructuras de datos
- **⚡ Algoritmo inteligente** - Cruce preciso de materiales por código
- **📈 Control de inventario** - Ajuste progresivo del stock
- **📱 Visualización avanzada** - Métricas y previsualización de datos
- **💾 Exportación** - Resultados en Excel optimizado

## 🚀 Requisitos

- Python 3.8 o superior
- Streamlit 1.45.1+
- Pandas 2.2.3+
- Openpyxl 3.1.5+
- XlsxWriter 3.2.3+
- Otras dependencias en `requirements.txt`

## ⚙️ Instalación

1. **Clonar el repositorio**
   ```bash
   git clone https://github.com/tuusuario/cruce-sap-dinamico.git
   cd cruce-sap-dinamico
   ```

2. **Crear y activar entorno virtual**
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # Linux/MacOS
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Instalar dependencias**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. **Configuración de autenticación**
   - Crea un archivo `.streamlit/secrets.toml` con:
   ```toml
   # Credenciales de Google OAuth2
   client_id = "tu-client-id.apps.googleusercontent.com"
   client_secret = "tu-client-secret"
   redirect_url = "http://localhost:8501"  # Cambiar en producción
   ```

## 🖥️ Uso

1. **Iniciar la aplicación**
   ```bash
   streamlit run main.py
   ```

2. **Acceder a la aplicación**
   - Abre tu navegador en: http://localhost:8501

3. **Autenticación**
   - Inicia sesión con tu cuenta de Google autorizada

4. **Cargar archivos**
   - Sube los archivos de descarga y existencia
   - Mapea las columnas según corresponda
   - Ejecuta el proceso de cruce

## 🔒 Seguridad

- Todas las credenciales se manejan a través de variables de entorno
- La autenticación utiliza OAuth2 con Google
- Se recomienda usar HTTPS en producción
- No compartir el archivo `secrets.toml`

## 🚀 Despliegue

### Opción 1: Streamlit Cloud (Recomendado)

1. Crea una cuenta en [Streamlit Cloud](https://streamlit.io/cloud)
2. Conecta tu repositorio de GitHub
3. Configura las variables de entorno en la sección de Settings
4. ¡Listo! Tu aplicación estará en línea

### Opción 2: Auto-hospedado

1. Configura un servidor con Python 3.8+
2. Clona el repositorio
3. Instala dependencias
4. Configura un proxy inverso (Nginx/Apache)
5. Usa un proceso manager como PM2 o Supervisor

## 📝 Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo `LICENSE` para más detalles.

## 🤝 Contribuir

1. Haz un Fork del proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Haz commit de tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Haz push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📞 Soporte

Para soporte, por favor abre un issue en el repositorio o contacta al equipo de desarrollo.

---

Desarrollado con ❤️ por Orlando Opsino H- [@orlando2019](https://github.com/orlando2019)
   ```

## Estructura de Archivos

```
CruceSAP_Dinamico/
├── main.py              # Aplicación principal de Streamlit
├── auth_system.py       # Sistema de autenticación
├── requirements.txt     # Dependencias del proyecto
└── README.md            # Este archivo
```

## Uso Detallado

### 1. Autenticación

- Al iniciar la aplicación, se solicitará iniciar sesión con su cuenta Google
- Una vez autenticado, tendrá acceso completo a la funcionalidad

### 2. Carga de Archivo

- Suba un archivo Excel que contenga al menos dos hojas:
  - Una hoja con los **materiales por descargar** (lista de pedidos)
  - Una hoja con la **existencia SAP** (inventario actual)
- El sistema aceptará diferentes formatos y estructuras de archivo

### 3. Selección de Hojas

- Seleccione las hojas correspondientes en la barra lateral:
  - Hoja para materiales por descargar
  - Hoja para existencia SAP

### 4. Mapeo de Columnas

- La aplicación permite mapear columnas de su archivo con las columnas requeridas:
  
  **Columnas para Materiales por Descargar:**
  - Item (identificador único)
  - MATERIAL (código del material)
  - Descripcion Material
  - CODIGO OBRA SGT
  - Planilla (nombre de la planilla)
  - Planilla Cantidad (cantidad solicitada)
  
  **Columnas para Existencia SAP:**
  - Item (identificador único)
  - Descripcion_SAP
  - SAP (cantidad en stock)

### 5. Procesamiento

- Haga clic en "Procesar Cruce" para iniciar el algoritmo
- El sistema realizará:
  - Cruce de materiales por código de ítem
  - División de líneas cuando el stock sea insuficiente
  - Ajuste progresivo del inventario SAP

### 6. Resultados

- Visualice los resultados con métricas clave:
  - Total de filas generadas
  - Suma total de diferencias
  - Cantidad de items descargables
- Examine la vista previa de los datos resultantes

### 7. Exportación

- Descargue el resultado completo como archivo Excel mediante el botón "Descargar Resultado"

## Algoritmo de Cruce

El algoritmo implementa la siguiente lógica:

1. Estandarización de columnas de entrada mediante mapeo dinámico
2. Conversión de valores numéricos para cantidades y stock
3. Cruce de datos por código de ítem
4. Procesamiento secuencial de filas para ajustar stock progresivamente
5. División automática de líneas cuando la cantidad solicitada excede el stock disponible
6. Etiquetado de registros como 'Descargable' si/no según disponibilidad
7. Cálculo de métricas y totales

## Solución de Problemas

- **Error en carga de archivo**: Verifique que su Excel tenga el formato correcto
- **Problemas con mapeo de columnas**: Asegúrese de que todas las columnas requeridas estén presentes
- **Resultados inesperados**: Revise el formato de los datos numéricos en su archivo de entrada
- **Error de autenticación**: Compruebe la configuración de credenciales y permisos

## Contacto y Soporte

Para soporte o reportar problemas, por favor contacte al administrador del sistema.
