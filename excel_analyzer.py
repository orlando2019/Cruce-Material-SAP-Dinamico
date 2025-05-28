# excel_analyzer.py
import pandas as pd
import tempfile
import os
from typing import Dict, Union, Optional
import streamlit as st


class ExcelAnalyzer:
    """
    Clase para analizar archivos Excel y mostrar información sobre su estructura y contenido.
    """

    def __init__(self, file_path: Optional[str] = None):
        """
        Inicializa el analizador de Excel.

        Args:
            file_path (str, opcional): Ruta al archivo Excel. Puede ser None si se usará un archivo cargado.
        """
        self.file_path = file_path
        self.temp_file_path = None
        self.sheet_names = []
        self.current_sheet = 0
        self.df = None
        self.file_loaded = False

    def load_file(self, uploaded_file) -> bool:
        """
        Carga un archivo Excel desde un objeto de archivo cargado.

        Args:
            uploaded_file: Objeto de archivo cargado con Streamlit.

        Returns:
            bool: True si el archivo se cargó correctamente, False en caso contrario.
        """
        try:
            # Crear archivo temporal
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                self.temp_file_path = tmp_file.name

            # Cargar información básica del archivo
            with pd.ExcelFile(self.temp_file_path) as excel_file:
                self.sheet_names = excel_file.sheet_names
                self.file_path = uploaded_file.name
                self.file_loaded = True
                return True

        except Exception as e:
            st.error(f"Error al cargar el archivo: {str(e)}")
            self._cleanup_temp_file()
            return False

    def get_sheet_info(self, sheet_name: Union[str, int] = 0) -> Dict:
        """
        Obtiene información detallada sobre una hoja específica.

        Args:
            sheet_name (str o int): Nombre o índice de la hoja.

        Returns:
            dict: Diccionario con información de la hoja.
        """
        if not self.file_loaded:
            raise ValueError("No hay ningún archivo cargado")

        try:
            # Leer solo los encabezados para mayor eficiencia
            df = pd.read_excel(self.temp_file_path, sheet_name=sheet_name, nrows=0)

            # Leer muestra de datos para análisis de tipos
            df_sample = pd.read_excel(
                self.temp_file_path, sheet_name=sheet_name, nrows=10
            )

            # Obtener información detallada de columnas
            columns_info = []
            for col in df.columns:
                col_type = str(df_sample[col].dtype)
                non_null_count = df_sample[col].count()
                null_count = len(df_sample) - non_null_count

                columns_info.append(
                    {
                        "nombre": col,
                        "tipo": col_type,
                        "no_nulos": non_null_count,
                        "nulos": null_count,
                        "ejemplo": df_sample[col].iloc[0]
                        if non_null_count > 0
                        else None,
                    }
                )

            return {
                "nombre_hoja": sheet_name
                if isinstance(sheet_name, str)
                else self.sheet_names[sheet_name],
                "total_filas": len(
                    pd.read_excel(self.temp_file_path, sheet_name=sheet_name)
                ),
                "total_columnas": len(df.columns),
                "columnas": columns_info,
                "hojas_disponibles": self.sheet_names,
            }

        except Exception as e:
            raise Exception(f"Error al leer la hoja {sheet_name}: {str(e)}")

    def get_data_preview(
        self, sheet_name: Union[str, int] = 0, n_rows: int = 5
    ) -> pd.DataFrame:
        """
        Obtiene una vista previa de los datos (con columnas a mayúsculas y columnas extra personalizadas).
        """
        if not self.file_loaded:
            raise ValueError("No hay ningún archivo cargado")
        try:
            df = pd.read_excel(
                self.temp_file_path,
                sheet_name=sheet_name,
                nrows=n_rows,
                dtype=str,
                engine="openpyxl",
            )
            df.columns = [c.upper() for c in df.columns]
            df = self.add_custom_columns(df)
            return df
        except Exception as e:
            raise Exception(f"Error al obtener vista previa: {str(e)}")

        """
        Obtiene una vista previa de los datos.

        Args:
            sheet_name (str o int): Nombre o índice de la hoja.
            n_rows (int): Número de filas a mostrar.

        Returns:
            pd.DataFrame: DataFrame con la vista previa.
        """
        if not self.file_loaded:
            raise ValueError("No hay ningún archivo cargado")

        try:
            return pd.read_excel(
                self.temp_file_path, sheet_name=sheet_name, nrows=n_rows
            )
        except Exception as e:
            raise Exception(f"Error al obtener vista previa: {str(e)}")

    def _cleanup_temp_file(self):
        """Limpia el archivo temporal si existe."""
        if self.temp_file_path and os.path.exists(self.temp_file_path):
            try:
                os.unlink(self.temp_file_path)
                self.temp_file_path = None
            except Exception as e:
                st.warning(f"No se pudo eliminar el archivo temporal: {str(e)}")

    def add_custom_columns(self, df):
        """
        Agrega las columnas personalizadas 'Obra-item' y 'OBRA Y TRABAJO'.
        """
        col_doc = "TEXTO CAB.DOCUMENTO"
        col_item = "ITEM"
        if col_doc in df.columns:
            # Extraer el número largo de 'TEXTO CAB.DOCUMENTO'
            df["__NUM_OBRA"] = df[col_doc].str.extract(r"(\\d{15,17})")
            # OBRA Y TRABAJO: 207012022100002-20
            df["OBRA Y TRABAJO"] = df["__NUM_OBRA"].apply(
                lambda x: f"{x[:-2]}-{x[-2:]}"
                if isinstance(x, str) and len(x) > 2
                else ""
            )
            # Obra-item: 20701202210000220-1110073
            if col_item in df.columns:
                df["Obra-item"] = df.apply(
                    lambda row: f"{row['__NUM_OBRA']}-{row[col_item]}"
                    if pd.notna(row["__NUM_OBRA"]) and pd.notna(row[col_item])
                    else "",
                    axis=1,
                )
            df.drop(columns=["__NUM_OBRA"], inplace=True)
        return df

    def excel_to_csv_and_load(self, sheet_name: Union[str, int] = 0) -> pd.DataFrame:
        """
        Convierte el Excel subido a CSV temporalmente y carga el DataFrame desde ese CSV para mejor rendimiento.
        """
        if not self.file_loaded:
            raise ValueError("No hay ningún archivo cargado")
        try:
            df = pd.read_excel(
                self.temp_file_path, sheet_name=sheet_name, dtype=str, engine="openpyxl"
            )
            df.columns = [c.upper() for c in df.columns]
            df = self.add_custom_columns(df)
            temp_csv = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
            df.to_csv(temp_csv.name, index=False)
            df_csv = pd.read_csv(temp_csv.name, dtype=str)
            temp_csv.close()
            return df_csv
        except Exception as e:
            raise Exception(f"Error al convertir y cargar como CSV: {str(e)}")

    def filter_by_almacen(self, df, almacen: str) -> pd.DataFrame:
        """
        Filtra el DataFrame por el almacén seleccionado (solo uno).
        """
        if "ALMACÉN" in df.columns and almacen:
            return df[df["ALMACÉN"] == almacen].copy()
        return df

    def export_to_excel(self, df, filename: str) -> str:
        """
        Exporta el DataFrame filtrado a un archivo Excel y retorna la ruta temporal.
        """
        temp_path = os.path.join(tempfile.gettempdir(), filename)
        df.to_excel(temp_path, index=False)
        return temp_path

    def list_columns(self, df) -> list:
        """
        Retorna solo la lista de nombres de columnas del DataFrame.
        """
        return list(df.columns)

    def __del__(self):
        """Destructor para limpieza de archivos temporales."""
        self._cleanup_temp_file()
