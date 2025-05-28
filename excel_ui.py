# excel_ui.py
import streamlit as st
from typing import Dict, Any
from excel_analyzer import ExcelAnalyzer


class ExcelUI:
    """
    Clase para manejar la interfaz de usuario del visor de Excel.
    """

    def __init__(self):
        """Inicializa la interfaz de usuario del visor de Excel."""
        if "excel_analyzer" not in st.session_state:
            st.session_state.excel_analyzer = None

    def render_uploader(self) -> bool:
        """
        Renderiza el componente de carga de archivos.

        Returns:
            bool: True si se cargó un archivo, False en caso contrario.
        """
        st.title("📊 Visor de Archivos Excel")

        st.markdown("""
        Carga un archivo Excel para analizar su estructura y contenido. 
        Esta herramienta te permitirá:
        - Ver todas las hojas del archivo
        - Analizar la estructura de columnas
        - Previsualizar los datos
        - Identificar tipos de datos y valores nulos
        """)

        uploaded_file = st.file_uploader(
            "Sube un archivo Excel",
            type=["xlsx", "xls"],
            help="Selecciona un archivo Excel para analizar su estructura",
        )

        if uploaded_file is not None:
            # Inicializar el analizador
            st.session_state.excel_analyzer = ExcelAnalyzer()
            if st.session_state.excel_analyzer.load_file(uploaded_file):
                return True
            else:
                st.session_state.excel_analyzer = None
                return False
        return False

    def render_sheet_selector(self, sheet_names: list) -> int:
        """
        Renderiza el selector de hojas.

        Args:
            sheet_names (list): Lista de nombres de hojas.

        Returns:
            int: Índice de la hoja seleccionada.
        """
        if len(sheet_names) > 1:
            tab_titles = [f"Hoja {i + 1}: {name}" for i, name in enumerate(sheet_names)]
            selected_tab = st.radio(
                "Selecciona una hoja:",
                range(len(sheet_names)),
                format_func=lambda x: tab_titles[x],
            )
            return selected_tab
        return 0

    def render_sheet_info(self, sheet_info: Dict[str, Any]):
        """
        Renderiza la información de una hoja.

        Args:
            sheet_info (dict): Información de la hoja.
        """
        # Mostrar información general
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("📄 Hoja", sheet_info["nombre_hoja"])
        with col2:
            st.metric("📊 Columnas", sheet_info["total_columnas"])
        with col3:
            st.metric("📈 Filas", sheet_info["total_filas"])

        # Mostrar tabla de columnas
        st.subheader("🔍 Análisis de Columnas")
        self._render_columns_table(sheet_info["columnas"])

    def _render_columns_table(self, columns: list):
        """
        Renderiza la tabla de columnas.

        Args:
            columns (list): Lista de diccionarios con información de columnas.
        """
        import pandas as pd

        # Crear DataFrame para mostrar
        df_columns = pd.DataFrame(columns)
        df_columns["nulos"] = (
            df_columns["nulos"].astype(str)
            + " ("
            + (
                df_columns["nulos"]
                / (df_columns["no_nulos"] + df_columns["nulos"])
                * 100
            )
            .round(1)
            .astype(str)
            + "%)"
        )
        df_columns = df_columns.rename(
            columns={
                "nombre": "Columna",
                "tipo": "Tipo de dato",
                "nulos": "Valores nulos",
                "ejemplo": "Ejemplo",
            }
        )

        # Mostrar tabla
        st.dataframe(
            df_columns[["Columna", "Tipo de dato", "Valores nulos", "Ejemplo"]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Columna": st.column_config.TextColumn("Columna", width="medium"),
                "Tipo de dato": st.column_config.TextColumn("Tipo", width="small"),
                "Valores nulos": st.column_config.TextColumn("Nulos", width="small"),
                "Ejemplo": st.column_config.TextColumn("Ejemplo", width="medium"),
            },
        )

    def render_data_preview(self, df_preview):
        """
        Renderiza la vista previa de los datos.

        Args:
            df_preview (pd.DataFrame): DataFrame con la vista previa.
        """
        st.subheader("📋 Vista previa de los datos")
        st.dataframe(df_preview, use_container_width=True)

    def show_error(self, message: str):
        """
        Muestra un mensaje de error.

        Args:
            message (str): Mensaje de error a mostrar.
        """
        st.error(f"❌ Error: {message}")

    def show_warning(self, message: str):
        """
        Muestra un mensaje de advertencia.

        Args:
            message (str): Mensaje de advertencia a mostrar.
        """
        st.warning(f"⚠️ {message}")

    def show_success(self, message: str):
        """
        Muestra un mensaje de éxito.

        Args:
            message (str): Mensaje de éxito a mostrar.
        """
        st.success(f"✅ {message}")

    def render_ui(self):
        """
        Renderiza la interfaz de usuario completa.
        """
        try:
            if self.render_uploader() and st.session_state.excel_analyzer:
                analyzer = st.session_state.excel_analyzer

                # Obtener información de la hoja actual
                sheet_info = analyzer.get_sheet_info(0)  # Por defecto primera hoja

                # Mostrar selector de hojas si hay más de una
                if len(sheet_info["hojas_disponibles"]) > 1:
                    selected_sheet = self.render_sheet_selector(
                        sheet_info["hojas_disponibles"]
                    )
                    sheet_info = analyzer.get_sheet_info(selected_sheet)
                else:
                    selected_sheet = sheet_info["nombre_hoja"]

                # Convertir a CSV y cargar desde CSV para mejor rendimiento
                try:
                    df_full = analyzer.excel_to_csv_and_load(selected_sheet)
                except Exception as e:
                    self.show_error(f"No se pudo convertir a CSV ni cargar: {str(e)}")
                    return

                # Listar solo los nombres de columnas
                st.info("Columnas encontradas en el archivo:")
                st.write(", ".join(analyzer.list_columns(df_full)))

                # Selección de almacén (solo uno, tipo selectbox)
                if "ALMACÉN" in df_full.columns:
                    almacenes_unicos = sorted(
                        df_full["ALMACÉN"].dropna().unique().tolist()
                    )
                    almacen_sel = st.selectbox(
                        "Selecciona un almacén para filtrar:",
                        almacenes_unicos,
                        help="Selecciona un almacén para mostrar solo sus datos.",
                    )
                    df_filtrado = analyzer.filter_by_almacen(df_full, almacen_sel)
                    st.markdown(f"**Almacén seleccionado:** {almacen_sel}")
                else:
                    st.warning("No se encontró la columna 'ALMACÉN' en el archivo.")
                    df_filtrado = df_full

                # Mostrar tabla filtrada (incluyendo Obra-item)
                st.subheader(":clipboard: Datos filtrados por almacén")
                st.dataframe(df_filtrado, use_container_width=True)

                # Botón para exportar a Excel
                if st.button(
                    "Exportar a Excel",
                    help="Descarga los datos filtrados en un archivo Excel",
                ):
                    nombre_archivo = "exportado_almacen.xlsx"
                    ruta_export = analyzer.export_to_excel(df_filtrado, nombre_archivo)
                    with open(ruta_export, "rb") as f:
                        st.download_button(
                            label="Descargar archivo Excel",
                            data=f,
                            file_name=nombre_archivo,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        )

        except Exception as e:
            self.show_error(f"Error en la interfaz: {str(e)}")
            if "analyzer" in locals():
                analyzer._cleanup_temp_file()
