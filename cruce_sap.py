import pandas as pd
import streamlit as st
from io import BytesIO

# --- Nombres de columna ESTÁNDAR que la lógica de negocio espera ---
EXPECTED_COLS_DESC = {
    "item_id_desc": "Item",
    "material_code": "MATERIAL",
    "description_desc": "Descripcion Material",
    "codigo_obra_sgt": "CODIGO OBRA SGT",
    "planilla_name": "Planilla",
    "quantity_planilla": "Planilla Cantidad",
}

EXPECTED_COLS_EXIST = {
    "item_id_exist": "Item",
    # Para evitar colisión si el usuario mapea la misma col
    "description_exist": "Descripcion_SAP",
    "stock_sap_qty": "SAP",
}


# --- Lógica de Negocio (adaptada con la nueva lógica de split) ---
def cruce_material_sap_procesado_con_split(df_desc_std: pd.DataFrame, df_exist_std: pd.DataFrame):
    """
    Realiza el cruce de materiales, ajusta el stock SAP de forma progresiva,
    y divide las líneas si la cantidad de la planilla excede el stock.
    """
    # Nombres de columna estandarizados que usaremos internamente
    col_item = EXPECTED_COLS_DESC["item_id_desc"]  # "Item"
    col_material = EXPECTED_COLS_DESC["material_code"]  # "MATERIAL"  # noqa: F841
    col_desc_planilla = EXPECTED_COLS_DESC["description_desc"]  # "Descripcion"
    col_planilla = EXPECTED_COLS_DESC["planilla_name"]  # "Planilla"
    # "Planilla Cantidad" (nombre para la entrada)
    col_qty_planilla_orig = EXPECTED_COLS_DESC["quantity_planilla"]

    # "SAP" (nombre para la entrada de stock)
    col_sap_stock_input = EXPECTED_COLS_EXIST["stock_sap_qty"]

    # 1. Validaciones de columnas de entrada (ya deberían estar estandarizadas)
    # (Se pueden omitir si confiamos en el mapeo, pero es bueno tenerlas)
    for expected_col_key, expected_col_val in EXPECTED_COLS_DESC.items():
        if expected_col_val not in df_desc_std.columns:
            st.error(
                f"Error interno: La columna estandarizada '{expected_col_val}' (de {expected_col_key}) falta en los datos de descarga."
            )
            return None
    for expected_col_key, expected_col_val in EXPECTED_COLS_EXIST.items():
        if expected_col_val not in df_exist_std.columns:
            st.error(
                f"Error interno: La columna estandarizada '{expected_col_val}' (de {expected_col_key}) falta en los datos de existencia."
            )
            return None

    # 2. Conversión a numérico
    df_desc_std[col_qty_planilla_orig] = pd.to_numeric(
        df_desc_std[col_qty_planilla_orig], errors="coerce"
    ).fillna(0)
    df_exist_std[col_sap_stock_input] = pd.to_numeric(
        df_exist_std[col_sap_stock_input], errors="coerce"
    ).fillna(0)

    # 3. Merge por Item
    # "Descripcion_SAP"
    col_desc_sap = EXPECTED_COLS_EXIST["description_exist"]
    df_merged = pd.merge(
        df_desc_std,  # Tomamos todas las columnas estandarizadas de df_desc_std
        # Item, SAP y Descripcion de existencia
        df_exist_std[[col_item, col_sap_stock_input, col_desc_sap]],
        on=col_item,
        how="left",
    )

    # Asegurarnos de que las columnas necesarias existan para evitar errores
    col_codigo_obra = EXPECTED_COLS_DESC["codigo_obra_sgt"]

    # Si la columna de descripción original existe, usarla como código de obra
    # SGT
    if col_desc_planilla in df_merged.columns:
        df_merged[col_codigo_obra] = df_merged[col_desc_planilla]
    else:
        # Si no existe, crear una columna vacía
        df_merged[col_codigo_obra] = ""

    # Si existen ambas columnas de descripción, usar la de SAP
    if col_desc_sap in df_merged.columns and col_desc_planilla in df_merged.columns:
        # Usar la descripción de SAP (Texto breve de material) como descripción
        # principal
        df_merged[col_desc_planilla] = df_merged[col_desc_sap]
    elif col_desc_sap in df_merged.columns:
        # Si solo existe descripción de SAP, crearla en ambas columnas
        df_merged[col_desc_planilla] = df_merged[col_desc_sap]
    elif col_desc_planilla not in df_merged.columns:
        # Si no existe ninguna descripción, crear columna vacía
        df_merged[col_desc_planilla] = ""

    # Renombrar la columna de stock SAP de entrada para evitar confusión con
    # la columna de salida
    df_merged.rename(columns={col_sap_stock_input: "SAP_Inicial_Item"}, inplace=True)
    df_merged["SAP_Inicial_Item"] = df_merged["SAP_Inicial_Item"].fillna(0)

    # 4. Extraer número de planilla para orden
    df_merged["NumPlanilla"] = (
        df_merged[col_planilla]
        .astype(str)
        .str.extract(r"^(\d+)")[0]  # Toma solo el primer grupo capturado
        .astype(float)
        .fillna(99999)  # Para planillas sin número al inicio, van al final
        .astype(int)
    )
    df_merged.sort_values([col_item, "NumPlanilla"], inplace=True)

    # 5. Procesar por ítem y dividir líneas excedentes
    processed_rows = []
    for _, group in df_merged.groupby(col_item, sort=False):
        # Stock inicial para este Item
        stock_actual_item = group.iloc[0]["SAP_Inicial_Item"]

        for idx, row_original in group.iterrows():
            # Convertir la fila a diccionario para facilitar la manipulación
            # Usamos .copy() para no modificar el diccionario base entre
            # iteraciones de split
            r_dict_base = row_original.to_dict().copy()

            # Cantidad solicitada por la planilla actual
            cantidad_solicitada_planilla = r_dict_base[col_qty_planilla_orig]

            # Crear una copia del diccionario para la fila actual que vamos a procesar
            # Esto es importante porque r_dict_base mantiene los valores originales de la planilla
            # mientras que r_modificable se altera si hay splits.
            r_modificable = r_dict_base.copy()

            sap_antes_procesar_esta_planilla = stock_actual_item

            if cantidad_solicitada_planilla == 0:
                r_modificable.update(
                    {
                        # 'Planilla Cantidad' ya es 0 desde r_dict_base
                        # Stock antes de esta planilla (no cambia)
                        "SAP Antes": sap_antes_procesar_esta_planilla,
                        "Diferencia": 0,
                        "SAP Restante": sap_antes_procesar_esta_planilla,  # Stock no cambia
                        "Descargable": "No",
                    }
                )
                processed_rows.append(r_modificable)
                # stock_actual_item no cambia porque no se descargó nada
                continue

            # Stock suficiente para la cantidad solicitada
            if stock_actual_item >= cantidad_solicitada_planilla:
                r_modificable.update(
                    {
                        # 'Planilla Cantidad' es la cantidad_solicitada_planilla
                        "SAP Antes": sap_antes_procesar_esta_planilla,
                        "Diferencia": 0,
                        "SAP Restante": stock_actual_item
                        - cantidad_solicitada_planilla,
                        "Descargable": "Si",
                    }
                )
                processed_rows.append(r_modificable)
                stock_actual_item -= (
                    cantidad_solicitada_planilla  # Actualizar stock del ítem
                )
            else:  # Stock insuficiente, hay que dividir
                # Parte descargable (si hay algo de stock)
                if stock_actual_item > 0:
                    # Fila para la parte que SÍ se puede descargar
                    r_descargable = r_dict_base.copy()  # Copia de la planilla original
                    # Cantidad a descargar es el stock restante
                    r_descargable[col_qty_planilla_orig] = stock_actual_item
                    r_descargable.update(
                        {
                            # Stock antes de tocar esta planilla
                            "SAP Antes": sap_antes_procesar_esta_planilla,
                            "Diferencia": 0,
                            "SAP Restante": 0,  # Se consume todo el stock
                            "Descargable": "Si",
                        }
                    )
                    processed_rows.append(r_descargable)

                # Parte faltante
                cantidad_faltante = cantidad_solicitada_planilla - stock_actual_item

                # Fila para la parte que NO se puede descargar
                r_faltante = r_dict_base.copy()  # Copia de la planilla original
                # Cantidad es lo que falta
                r_faltante[col_qty_planilla_orig] = cantidad_faltante
                r_faltante.update(
                    {
                        "SAP Antes": 0,  # Ya no hay stock "antes" para esta parte faltante
                        "Diferencia": cantidad_faltante,
                        "SAP Restante": 0,  # Sigue siendo 0
                        "Descargable": "No",
                    }
                )
                processed_rows.append(r_faltante)

                stock_actual_item = 0  # El stock del ítem se agota

    # 6. Construir DataFrame resultante
    df_final = pd.DataFrame(processed_rows)

    # 7. Limpieza y orden final de columnas
    if "NumPlanilla" in df_final.columns:
        df_final.drop(columns=["NumPlanilla"], inplace=True)
    if "SAP_Inicial_Item" in df_final.columns:  # Columna auxiliar del merge
        df_final.drop(columns=["SAP_Inicial_Item"], inplace=True)

    # Renombrar columnas estandarizadas a los nombres finales deseados si es necesario
    # En este caso, los nombres de EXPECTED_COLS_DESC ya coinciden con la salida deseada
    # excepto 'Planilla Cantidad' que es el nombre clave.
    # La columna de stock 'SAP Antes' ya se crea con ese nombre.

    final_column_order = [
        EXPECTED_COLS_DESC["item_id_desc"],  # Item
        EXPECTED_COLS_DESC["material_code"],  # MATERIAL
        EXPECTED_COLS_DESC["description_desc"],  # Descripcion
        EXPECTED_COLS_DESC["codigo_obra_sgt"],  # CODIGO OBRA SGT
        EXPECTED_COLS_DESC["planilla_name"],  # Planilla
        # Planilla Cantidad (este es el que puede cambiar si hay split)
        EXPECTED_COLS_DESC["quantity_planilla"],
        "SAP Antes",
        "Diferencia",
        "SAP Restante",
        "Descargable",
    ]

    # Asegurar que todas las columnas existen antes de intentar reordenar
    existing_final_cols = [col for col in final_column_order if col in df_final.columns]
    if not df_final.empty:
        df_final = df_final[existing_final_cols]
    else:  # Si df_final está vacío, crearlo con las columnas esperadas
        df_final = pd.DataFrame(columns=existing_final_cols)

    return df_final


# --- Función auxiliar para descargar Excel ---
def to_excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="CruceMaterialSAP_Split")
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
    if "prev_sheet_desc" in st.session_state:
        del st.session_state.prev_sheet_desc
    if "prev_sheet_exist" in st.session_state:
        del st.session_state.prev_sheet_exist
