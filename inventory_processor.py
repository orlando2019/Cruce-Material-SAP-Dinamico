import pandas as pd
from typing import Dict, Tuple, List, Any


class InventoryProcessor:
    """
    Procesa el cruce de inventario entre un archivo maestro
    y un archivo dinámico de descargas.
    """

    def __init__(
        self,
        master_path: str,
        dynamic_path: str,
        output_path: str,
        observation: str,
        new_work_order: str,
        new_job_number: str,
    ):
        # Inicializar rutas y parámetros dinámicos
        self.master_path = master_path
        self.dynamic_path = dynamic_path
        self.output_path = output_path
        self.observation = observation
        self.new_work_order = new_work_order
        # Formatear nuevo trabajo a 2 dígitos
        self.new_job_number = new_job_number.zfill(2)

        # Inicializar estructuras de datos
        self.master_df: pd.DataFrame = pd.DataFrame()
        self.dynamic_df: pd.DataFrame = pd.DataFrame()
        self.master_index: Dict[Tuple[Any, Any], Dict[str, Any]] = {}
        self.result_rows: List[Dict[str, Any]] = []

    def load_master(self):
        # Carga el archivo maestro y limpia filas innecesarias
        self.master_df = pd.read_excel(self.master_path)
        # Eliminar filas sin código de obra
        self.master_df = self.master_df[self.master_df["CODIGO OBRA SGT"].notna()]
        # Convertir FECHA DESCAR SGT a datetime
        self.master_df["FECHA DESCAR SGT"] = pd.to_datetime(
            self.master_df["FECHA DESCAR SGT"], dayfirst=True, errors="coerce"
        )
        # Crear índice de búsqueda para cruces rápidos
        self.master_index = {
            (row["CODIGO OBRA SGT"], row["Item"]): row.to_dict()
            for _, row in self.master_df.iterrows()
        }

    def load_dynamic(self):
        # Carga el archivo dinámico y normaliza la columna Descargable
        self.dynamic_df = pd.read_excel(self.dynamic_path)
        self.dynamic_df["Descargable"] = (
            self.dynamic_df["Descargable"].astype(str).str.strip().str.upper()
        )

    def process(self):
        # Procesa cada fila del archivo dinámico
        for _, drow in self.dynamic_df.iterrows():
            key = (drow["CODIGO OBRA SGT"], drow["Item"])
            record = self.master_index.pop(key, None)
            if not record:
                continue

            qty = drow["Planilla Cantidad"]
            if drow["Descargable"] not in ("si", "sí"):
                # Sin descarga, conservar registro intacto
                self.result_rows.append(record)
                continue

            saldo = record.get("SALDO", 0)
            recs: List[Dict[str, Any]] = []
            if saldo >= qty:
                # Stock suficiente para descargar todo
                recs.append(
                    {
                        **record,
                        "Cant Desc.": qty,
                        "SALDO": saldo - qty,
                        "CRUZADO": "SI" if saldo - qty == 0 else "NO",
                    }
                )
            else:
                # Stock insuficiente → dividir entrada y déficit
                used = max(saldo, 0)
                deficit = qty - used
                recs.append({**record, "Cant Desc.": used, "SALDO": 0, "CRUZADO": "SI"})
                recs.append(
                    {
                        **record,
                        "Cant Desc.": deficit,
                        "SALDO": -deficit,
                        "CRUZADO": "NO",
                    }
                )

            # Añadir datos adicionales en cada registro
            for rec in recs:
                rec["OBSERVACION"] = self.observation
                rec["NUEVA OBRA"] = self.new_work_order
                rec["NUEVO TRABAJO"] = self.new_job_number
                # Construir código compuesto dinámico
                rec["OBRA - TRAB - ITEM"] = (
                    f"{self.new_work_order}{self.new_job_number}-{rec['Item']}"
                )
                # Formatear fecha a dd/mm/yyyy o dejar vacío
                fecha = rec.get("FECHA DESCAR SGT")
                rec["FECHA DESCAR SGT"] = (
                    fecha.strftime("%d/%m/%Y") if pd.notna(fecha) else ""
                )
                self.result_rows.append(rec)

        # Agregar registros restantes del maestro no procesados
        self.result_rows.extend(self.master_index.values())

    def save(self):
        # Construir DataFrame final
        df = pd.DataFrame(self.result_rows)
        # Eliminar duplicados exactos
        df = df.drop_duplicates()
        # Asegurar filas válidas y formato de nuevo trabajo
        df = df[df["CODIGO OBRA SGT"].notna()]
        df["NUEVO TRABAJO"] = df["NUEVO TRABAJO"].astype(str).str.zfill(2)
        # Guardar Excel final
        df.to_excel(self.output_path, index=False)

    def run(self):
        self.load_master()
        self.load_dynamic()
        self.process()
        self.save()
        print(f"✅ Archivo generado: {self.output_path}")


def main():
    processor = InventoryProcessor(
        master_path="PRUEBA MATERIAL NO CRUZADO 2025.xlsx",
        dynamic_path="PRUEBA MATERIAL NO CRUZADO 27-05-2025.xlsx",
        output_path="inventario_cruzado_final.xlsx",
        observation="PLANILLA DESCARGUE MATERIAL",
        new_work_order="206012025020002",
        new_job_number="3",
    )
    processor.run()


if __name__ == "__main__":
    main()
