import streamlit as st
import pandas as pd
import re
import os
from io import BytesIO
from auth_system import check_auth, get_logout_button

# Inicializar session_state para evitar errores
if 'email' not in st.session_state:
    st.session_state.email = None

# Configuración de la página (DEBE ser la primera instrucción de Streamlit)
st.set_page_config(
        layout="wide", 
        page_title="Cruce de Material SAP Dinámico",
        page_icon="🧊"
        )

# --- Sistema de Autenticación con Google (simplificado) ---
# Simple verificación de autenticación - mostrará la página de login si es necesario
check_auth()

# --- Nombres de columna ESTÁNDAR que la lógica de negocio espera ---
EXPECTED_COLS_DESC = {
    "item_id_desc": "Item",
    "material_code": "MATERIAL",
    "description_desc": "Descripcion Material",
    "codigo_obra_sgt": "CODIGO OBRA SGT",
    "planilla_name": "Planilla",
    "quantity_planilla": "Planilla Cantidad"
}

EXPECTED_COLS_EXIST = {
    "item_id_exist": "Item",
    "description_exist": "Descripcion_SAP", # Para evitar colisión si el usuario mapea la misma col
    "stock_sap_qty": "SAP"
}

# --- Lógica de Negocio (adaptada con la nueva lógica de split) ---
def cruce_material_sap_procesado_con_split(
    df_desc_std: pd.DataFrame,
    df_exist_std: pd.DataFrame
):
    """
    Realiza el cruce de materiales, ajusta el stock SAP de forma progresiva,
    y divide las líneas si la cantidad de la planilla excede el stock.
    """
    # Nombres de columna estandarizados que usaremos internamente
    col_item = EXPECTED_COLS_DESC["item_id_desc"]              # "Item"
    col_material = EXPECTED_COLS_DESC["material_code"]        # "MATERIAL"
    col_desc_planilla = EXPECTED_COLS_DESC["description_desc"]# "Descripcion"
    col_planilla = EXPECTED_COLS_DESC["planilla_name"]        # "Planilla"
    col_qty_planilla_orig = EXPECTED_COLS_DESC["quantity_planilla"] # "Planilla Cantidad" (nombre para la entrada)
    
    col_sap_stock_input = EXPECTED_COLS_EXIST["stock_sap_qty"] # "SAP" (nombre para la entrada de stock)

    # 1. Validaciones de columnas de entrada (ya deberían estar estandarizadas)
    # (Se pueden omitir si confiamos en el mapeo, pero es bueno tenerlas)
    for expected_col_key, expected_col_val in EXPECTED_COLS_DESC.items():
        if expected_col_val not in df_desc_std.columns:
            st.error(f"Error interno: La columna estandarizada '{expected_col_val}' (de {expected_col_key}) falta en los datos de descarga.")
            return None
    for expected_col_key, expected_col_val in EXPECTED_COLS_EXIST.items():
        if expected_col_val not in df_exist_std.columns:
            st.error(f"Error interno: La columna estandarizada '{expected_col_val}' (de {expected_col_key}) falta en los datos de existencia.")
            return None

    # 2. Conversión a numérico
    df_desc_std[col_qty_planilla_orig] = pd.to_numeric(df_desc_std[col_qty_planilla_orig], errors='coerce').fillna(0)
    df_exist_std[col_sap_stock_input] = pd.to_numeric(df_exist_std[col_sap_stock_input], errors='coerce').fillna(0)

    # 3. Merge por Item
    col_desc_sap = EXPECTED_COLS_EXIST["description_exist"] # "Descripcion_SAP"
    df_merged = pd.merge(
        df_desc_std, # Tomamos todas las columnas estandarizadas de df_desc_std
        df_exist_std[[col_item, col_sap_stock_input, col_desc_sap]], # Item, SAP y Descripcion de existencia
        on=col_item,
        how='left'
    )
    
    # Asegurarnos de que las columnas necesarias existan para evitar errores
    col_codigo_obra = EXPECTED_COLS_DESC["codigo_obra_sgt"]
    
    # Si la columna de descripción original existe, usarla como código de obra SGT
    if col_desc_planilla in df_merged.columns:
        df_merged[col_codigo_obra] = df_merged[col_desc_planilla]
    else:
        # Si no existe, crear una columna vacía
        df_merged[col_codigo_obra] = ""
    
    # Si existen ambas columnas de descripción, usar la de SAP
    if col_desc_sap in df_merged.columns and col_desc_planilla in df_merged.columns:
        # Usar la descripción de SAP (Texto breve de material) como descripción principal
        df_merged[col_desc_planilla] = df_merged[col_desc_sap]
    elif col_desc_sap in df_merged.columns:
        # Si solo existe descripción de SAP, crearla en ambas columnas
        df_merged[col_desc_planilla] = df_merged[col_desc_sap]
    elif col_desc_planilla not in df_merged.columns:
        # Si no existe ninguna descripción, crear columna vacía
        df_merged[col_desc_planilla] = ""

    # Renombrar la columna de stock SAP de entrada para evitar confusión con la columna de salida
    df_merged.rename(columns={col_sap_stock_input: 'SAP_Inicial_Item'}, inplace=True)
    df_merged['SAP_Inicial_Item'] = df_merged['SAP_Inicial_Item'].fillna(0)


    # 4. Extraer número de planilla para orden
    df_merged['NumPlanilla'] = (
        df_merged[col_planilla].astype(str)
        .str.extract(r'^(\d+)')[0] # Toma solo el primer grupo capturado
        .astype(float)
        .fillna(99999) # Para planillas sin número al inicio, van al final
        .astype(int)
    )
    df_merged.sort_values([col_item, 'NumPlanilla'], inplace=True)

    # 5. Procesar por ítem y dividir líneas excedentes
    processed_rows = []
    for _, group in df_merged.groupby(col_item, sort=False):
        stock_actual_item = group.iloc[0]['SAP_Inicial_Item'] # Stock inicial para este Item
        
        for idx, row_original in group.iterrows():
            # Convertir la fila a diccionario para facilitar la manipulación
            # Usamos .copy() para no modificar el diccionario base entre iteraciones de split
            r_dict_base = row_original.to_dict().copy() 
            
            # Cantidad solicitada por la planilla actual
            cantidad_solicitada_planilla = r_dict_base[col_qty_planilla_orig]

            # Crear una copia del diccionario para la fila actual que vamos a procesar
            # Esto es importante porque r_dict_base mantiene los valores originales de la planilla
            # mientras que r_modificable se altera si hay splits.
            r_modificable = r_dict_base.copy()


            sap_antes_procesar_esta_planilla = stock_actual_item

            if cantidad_solicitada_planilla == 0:
                r_modificable.update({
                    # 'Planilla Cantidad' ya es 0 desde r_dict_base
                    'SAP Antes': sap_antes_procesar_esta_planilla, # Stock antes de esta planilla (no cambia)
                    'Diferencia': 0,
                    'SAP Restante': sap_antes_procesar_esta_planilla, # Stock no cambia
                    'Descargable': 'No'
                })
                processed_rows.append(r_modificable)
                # stock_actual_item no cambia porque no se descargó nada
                continue

            # Stock suficiente para la cantidad solicitada
            if stock_actual_item >= cantidad_solicitada_planilla:
                r_modificable.update({
                    # 'Planilla Cantidad' es la cantidad_solicitada_planilla
                    'SAP Antes': sap_antes_procesar_esta_planilla,
                    'Diferencia': 0,
                    'SAP Restante': stock_actual_item - cantidad_solicitada_planilla,
                    'Descargable': 'Si'
                })
                processed_rows.append(r_modificable)
                stock_actual_item -= cantidad_solicitada_planilla # Actualizar stock del ítem
            else: # Stock insuficiente, hay que dividir
                # Parte descargable (si hay algo de stock)
                if stock_actual_item > 0:
                    # Fila para la parte que SÍ se puede descargar
                    r_descargable = r_dict_base.copy() # Copia de la planilla original
                    r_descargable[col_qty_planilla_orig] = stock_actual_item # Cantidad a descargar es el stock restante
                    r_descargable.update({
                        'SAP Antes': sap_antes_procesar_esta_planilla, # Stock antes de tocar esta planilla
                        'Diferencia': 0,
                        'SAP Restante': 0, # Se consume todo el stock
                        'Descargable': 'Si'
                    })
                    processed_rows.append(r_descargable)
                
                # Parte faltante
                cantidad_faltante = cantidad_solicitada_planilla - stock_actual_item
                
                # Fila para la parte que NO se puede descargar
                r_faltante = r_dict_base.copy() # Copia de la planilla original
                r_faltante[col_qty_planilla_orig] = cantidad_faltante # Cantidad es lo que falta
                r_faltante.update({
                    'SAP Antes': 0, # Ya no hay stock "antes" para esta parte faltante
                    'Diferencia': cantidad_faltante,
                    'SAP Restante': 0, # Sigue siendo 0
                    'Descargable': 'No'
                })
                processed_rows.append(r_faltante)
                
                stock_actual_item = 0 # El stock del ítem se agota

    # 6. Construir DataFrame resultante
    df_final = pd.DataFrame(processed_rows)

    # 7. Limpieza y orden final de columnas
    if 'NumPlanilla' in df_final.columns:
        df_final.drop(columns=['NumPlanilla'], inplace=True)
    if 'SAP_Inicial_Item' in df_final.columns: # Columna auxiliar del merge
        df_final.drop(columns=['SAP_Inicial_Item'], inplace=True)

    # Renombrar columnas estandarizadas a los nombres finales deseados si es necesario
    # En este caso, los nombres de EXPECTED_COLS_DESC ya coinciden con la salida deseada
    # excepto 'Planilla Cantidad' que es el nombre clave.
    # La columna de stock 'SAP Antes' ya se crea con ese nombre.
    
    final_column_order = [
        EXPECTED_COLS_DESC["item_id_desc"],         # Item
        EXPECTED_COLS_DESC["material_code"],        # MATERIAL
        EXPECTED_COLS_DESC["description_desc"],     # Descripcion
        EXPECTED_COLS_DESC["codigo_obra_sgt"],     # CODIGO OBRA SGT
        EXPECTED_COLS_DESC["planilla_name"],        # Planilla
        EXPECTED_COLS_DESC["quantity_planilla"],    # Planilla Cantidad (este es el que puede cambiar si hay split)
        'SAP Antes',
        'Diferencia',
        'SAP Restante',
        'Descargable'
    ]
    
    # Asegurar que todas las columnas existen antes de intentar reordenar
    existing_final_cols = [col for col in final_column_order if col in df_final.columns]
    if not df_final.empty:
        df_final = df_final[existing_final_cols]
    else: # Si df_final está vacío, crearlo con las columnas esperadas
        df_final = pd.DataFrame(columns=existing_final_cols)


    return df_final


# --- Función auxiliar para descargar Excel ---
def to_excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='CruceMaterialSAP_Split')
    processed_data = output.getvalue()
    return processed_data

# --- Función para limpiar el estado ---
def limpiar_estado():
    # Reiniciar todas las variables de estado
    st.session_state.uploaded_file_obj = None
    st.session_state.sheet_names = []
    st.session_state.df_desc_cols = []
    st.session_state.df_exist_cols = []
    st.session_state.df_result = None
    st.session_state.processed_successfully = False
    
    # Eliminar las variables de mapeo
    for key_map in list(st.session_state.keys()):
        if key_map.startswith("map_desc_") or key_map.startswith("map_exist_"):
            del st.session_state[key_map]
    
    # Eliminar variables de selección de hojas
    if "prev_sheet_desc" in st.session_state: del st.session_state.prev_sheet_desc
    if "prev_sheet_exist" in st.session_state: del st.session_state.prev_sheet_exist

# --- Interfaz de Streamlit (igual que antes, pero llamará a la nueva lógica) ---
def main():
      
    # Encabezado y botones de la interfaz
    col_titulo, col_usuario, col_acciones = st.columns([3, 1, 1])
    
    with col_titulo:
        st.title("📊 Aplicación de Cruce de Material SAP Dinámico")
    
    with col_usuario:
        # Mostrar información del usuario autenticado con Google
        if 'email' in st.session_state and st.session_state.email:
            st.write(f"👤 **Usuario:** {st.session_state.email}")
    
    with col_acciones:
        col_limpiar, col_logout = st.columns(2)
        with col_limpiar:
            if st.button("Limpiar Todo",icon="🗑️", key="btn_limpiar", help="Limpiar Todo", type="secondary"):
                limpiar_estado()
                st.rerun()
        with col_logout:
            # Ahora usando nuestro sistema personalizado de logout
            get_logout_button()
    
    st.markdown("""
    Sube tu archivo Excel, selecciona las hojas y mapea las columnas.
    La aplicación ajustará el stock SAP progresivamente y dividirá las planillas si el stock es insuficiente.
    """)

    if "uploaded_file_obj" not in st.session_state:
        st.session_state.uploaded_file_obj = None
    if "sheet_names" not in st.session_state:
        st.session_state.sheet_names = []
    # ... (resto de inicializaciones de session_state como antes) ...
    if "df_desc_cols" not in st.session_state:
        st.session_state.df_desc_cols = []
    if "df_exist_cols" not in st.session_state:
        st.session_state.df_exist_cols = []
    if "df_result" not in st.session_state:
        st.session_state.df_result = None
    if "processed_successfully" not in st.session_state:
        st.session_state.processed_successfully = False


    uploaded_file = st.file_uploader(
        " Carga tu archivo Excel",
        type=["xlsx", "xls"],
        key="file_uploader_widget_split" 
    )

    if uploaded_file:
        if st.session_state.uploaded_file_obj is None or uploaded_file.name != st.session_state.uploaded_file_obj.name:
            st.session_state.uploaded_file_obj = uploaded_file
            st.session_state.sheet_names = []
            st.session_state.df_desc_cols = []
            st.session_state.df_exist_cols = []
            st.session_state.df_result = None
            st.session_state.processed_successfully = False
            for key_map in list(st.session_state.keys()):
                if key_map.startswith("map_desc_") or key_map.startswith("map_exist_"):
                    del st.session_state[key_map]
            if "prev_sheet_desc" in st.session_state: del st.session_state.prev_sheet_desc
            if "prev_sheet_exist" in st.session_state: del st.session_state.prev_sheet_exist
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
            try: default_idx_desc = [s.lower() for s in st.session_state.sheet_names].index('material por descargar')
            except ValueError: default_idx_desc = 0
        
        selected_sheet_desc = st.sidebar.selectbox("Hoja 'Material por Descargar'", st.session_state.sheet_names, index=default_idx_desc, key="sel_sheet_desc")

        default_idx_exist = 0
        if st.session_state.sheet_names:
            try: default_idx_exist = [s.lower() for s in st.session_state.sheet_names].index('existencia')
            except ValueError: default_idx_exist = 1 if len(st.session_state.sheet_names) > 1 else 0
        selected_sheet_exist = st.sidebar.selectbox("Hoja 'Existencia SAP'", st.session_state.sheet_names, index=default_idx_exist, key="sel_sheet_exist")

        try:
            if selected_sheet_desc and (not st.session_state.df_desc_cols or st.session_state.get("prev_sheet_desc") != selected_sheet_desc) :
                df_temp_desc = pd.read_excel(st.session_state.uploaded_file_obj, sheet_name=selected_sheet_desc, dtype=str)
                st.session_state.df_desc_cols = [""] + df_temp_desc.columns.tolist()
                st.session_state.prev_sheet_desc = selected_sheet_desc
            
            if selected_sheet_exist and (not st.session_state.df_exist_cols or st.session_state.get("prev_sheet_exist") != selected_sheet_exist):
                df_temp_exist = pd.read_excel(st.session_state.uploaded_file_obj, sheet_name=selected_sheet_exist, dtype=str)
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
                try: default_index = st.session_state.df_desc_cols.index(expected_col_name_std)
                except ValueError:
                    try: default_index = [c.lower() for c in st.session_state.df_desc_cols].index(expected_col_name_std.lower())
                    except ValueError:
                        original_common_name = ""
                        if key_internal == "item_id_desc": original_common_name = "Item"
                        elif key_internal == "material_code": original_common_name = "MATERIAL"
                        elif key_internal == "description_desc": 
                            # Para descripcion buscamos primero Texto breve de material si existe
                            try:
                                if "Texto breve de material" in st.session_state.df_desc_cols:
                                    original_common_name = "Texto breve de material"
                                else:
                                    original_common_name = "Descripción"
                            except:
                                original_common_name = "Descripción"
                        elif key_internal == "codigo_obra_sgt":
                            # Para codigo de obra buscamos varias opciones comunes
                            try:
                                if "CODIGO OBRA SGT" in st.session_state.df_desc_cols:
                                    original_common_name = "CODIGO OBRA SGT"
                                elif "CODIGO OBRA" in st.session_state.df_desc_cols:
                                    original_common_name = "CODIGO OBRA"
                                elif "Descripción" in st.session_state.df_desc_cols:
                                    original_common_name = "Descripción"
                                else:
                                    original_common_name = ""
                            except:
                                original_common_name = ""
                        elif key_internal == "planilla_name": original_common_name = "NOMBRE PLANILLA"
                        elif key_internal == "quantity_planilla": original_common_name = "Cantidad"
                        if original_common_name:
                            try: default_index = st.session_state.df_desc_cols.index(original_common_name)
                            except ValueError: 
                                try: default_index = [c.lower() for c in st.session_state.df_desc_cols].index(original_common_name.lower())
                                except ValueError: default_index = 0
                        else: default_index = 0
            # Usar colecciones estándar sin agregar columnas falsas que puedan causar problemas
            user_col_selection = st.sidebar.selectbox(f"{expected_col_name_std} (Descarga):", st.session_state.df_desc_cols, index=default_index, key=f"map_desc_{key_internal}")
            if user_col_selection: user_mappings_desc[expected_col_name_std] = user_col_selection

        st.sidebar.markdown("**Hoja 'Existencia SAP':**")
        for key_internal, expected_col_name_std in EXPECTED_COLS_EXIST.items():
            default_index = 0
            if st.session_state.df_exist_cols:
                try: default_index = st.session_state.df_exist_cols.index(expected_col_name_std)
                except ValueError:
                    try: default_index = [c.lower() for c in st.session_state.df_exist_cols].index(expected_col_name_std.lower())
                    except ValueError:
                        original_common_name = ""
                        if key_internal == "item_id_exist": original_common_name = "Item" # O 'ITEM'
                        elif key_internal == "description_exist": original_common_name = "Texto breve de material"
                        elif key_internal == "stock_sap_qty": original_common_name = "Libre utilización"
                        if original_common_name:
                            try: default_index = st.session_state.df_exist_cols.index(original_common_name)
                            except ValueError: 
                                try: default_index = [c.lower() for c in st.session_state.df_exist_cols].index(original_common_name.lower())
                                except ValueError: default_index = 0
                        else: default_index = 0
            user_col_selection = st.sidebar.selectbox(f"{expected_col_name_std} (Existencia):", st.session_state.df_exist_cols, index=default_index, key=f"map_exist_{key_internal}")
            if user_col_selection: user_mappings_exist[expected_col_name_std] = user_col_selection
        
        all_desc_mapped = len(user_mappings_desc) == len(EXPECTED_COLS_DESC)
        all_exist_mapped = len(user_mappings_exist) == len(EXPECTED_COLS_EXIST)
        if not all_desc_mapped: st.sidebar.warning("Mapea todas las columnas para 'Material por Descargar'.")
        if not all_exist_mapped: st.sidebar.warning("Mapea todas las columnas para 'Existencia SAP'.")

        if st.button("🚀 Procesar Cruce (con Split)", type="primary", key="process_button_split_key", disabled=not (all_desc_mapped and all_exist_mapped)):
            st.session_state.processed_successfully = False 
            st.session_state.df_result = None
            with st.spinner("Procesando con división de líneas..."):
                try:
                    df_desc_original = pd.read_excel(st.session_state.uploaded_file_obj, sheet_name=selected_sheet_desc, dtype=str)
                    df_exist_original = pd.read_excel(st.session_state.uploaded_file_obj, sheet_name=selected_sheet_exist, dtype=str)

                    df_desc_std = pd.DataFrame()
                    for expected_name_std, user_col_name in user_mappings_desc.items():
                        # Manejar el caso especial cuando se selecciona 'Texto breve de material'
                        # pero esa columna no existe en los datos originales
                        if user_col_name == "Texto breve de material" and user_col_name not in df_desc_original.columns:
                            # Si no existe, usamos una columna vacía
                            df_desc_std[expected_name_std] = ""
                        else:
                            df_desc_std[expected_name_std] = df_desc_original[user_col_name]
                    
                    df_exist_std = pd.DataFrame()
                    for expected_name_std, user_col_name in user_mappings_exist.items():
                        df_exist_std[expected_name_std] = df_exist_original[user_col_name]
                    
                    # *** LLAMADA A LA NUEVA LÓGICA ***
                    st.session_state.df_result = cruce_material_sap_procesado_con_split(df_desc_std, df_exist_std)
                    
                    if st.session_state.df_result is not None:
                        st.session_state.processed_successfully = True
                    else:
                        st.error("El procesamiento (con split) falló o no generó un DataFrame.")
                except Exception as e:
                    st.error(f"Error crítico durante el procesamiento (con split): {e}")
                    import traceback
                    st.error(traceback.format_exc())
                    st.session_state.df_result = None
                    st.session_state.processed_successfully = False

    # --- Mostrar resultados ---
    if st.session_state.processed_successfully and st.session_state.df_result is not None:
        if not st.session_state.df_result.empty:
            st.success("✅ ¡Proceso con división de líneas completado!")
            st.subheader("📋 Vista Previa del Resultado")
            st.dataframe(st.session_state.df_result.head(30)) # Mostrar más filas por si hay splits

            st.subheader("📊 Resumen del Resultado")
            col_res1, col_res2, col_res3 = st.columns(3)
            col_res1.metric("Total de Filas Generadas", len(st.session_state.df_result))
            if 'Diferencia' in st.session_state.df_result.columns:
                sum_diferencia = pd.to_numeric(st.session_state.df_result['Diferencia'], errors='coerce').sum()
                col_res2.metric("Suma Total de 'Diferencia'", f"{sum_diferencia:,.0f}")
            if 'Descargable' in st.session_state.df_result.columns:
                desc_si_count = (st.session_state.df_result['Descargable'] == 'Si').sum()
                desc_no_count = (st.session_state.df_result['Descargable'] == 'No').sum()
                col_res3.metric("Descargable 'Sí'", desc_si_count)
                # Podríamos añadir otra métrica para 'No' si es relevante
            
            excel_bytes = to_excel_bytes(st.session_state.df_result)
            st.download_button(
                label="📥 Descargar Resultado (con Split) como Excel",
                data=excel_bytes,
                file_name="Cruce_Material_SAP_Split_Streamlit.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_button_split_key"
            )
        else:
             st.warning("⚠️ El proceso se completó, pero el DataFrame resultante está vacío. Revisa datos y mapeos.")
             st.dataframe(st.session_state.df_result)
    elif st.session_state.uploaded_file_obj and not st.session_state.processed_successfully and st.session_state.df_result is None and st.session_state.get("process_button_split_key"):
        st.error("❌ El procesamiento (con split) no pudo completarse. Revisa mensajes.")
    if not st.session_state.uploaded_file_obj:
        st.info("Por favor, carga un archivo Excel.")

    st.markdown("---")

if __name__ == '__main__':
    main()