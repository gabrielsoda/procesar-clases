"""
Detecta videos en processed_videos_path con marker .uploaded
Borrar el mp4 + el .uploaded + el original en videos_dir
Preview interactivo antes de borrar
"""

from pathlib import Path
import re
import sys
import json
import argparse

# constantes
CONFIG_PATH = Path(__file__).parent / "config.json"
VIDEO_PROCESADO = re.compile(
    r"^(\d{4}-\d{2}-\d{2})_(\d+)([A-Z]{2,4})\.mp4$",
    re.IGNORECASE
)

# configuracion
def cargar_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"    [ERROR] No se encontró config.json en {CONFIG_PATH}")
        sys.exit(1)
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)
    
def detectar_limpiables(
        processed_dir: Path,
        videos_dir: Path,
        codigos_validos: set,
        extensiones: list,
        ) -> list:
    """itera los mp4 en processed_dir que matcheen VIDEO_PROCESADO
    Para cada uno chequea que existe el marker .mp4.uploaded
    Si no existe no es limpiable
    Busca el original en videos_dir con mismo nombre base pero con cualquier extension
    arma un dict por cada grupo con mp4 (Path), uploaded (Path), original (Path o None), fecha, num, codigo
    devuelve una lista ordenada por fecha y código"""
    limpiables = []
    for archivo in processed_dir.glob("*mp4"):
        m = VIDEO_PROCESADO.match(archivo.name + ".uploaded")
        print(archivo.name + ".uploaded") # !!!!!!!!!!!!!! hasta acá quedamos
        if not m:
            continue

    return limpiables

config = cargar_config()
processed_dir = Path(config["processed_videos_path"])
videos_dir = Path(config["videos_dir"])
materias = config["materias"]
codigos_validos = set(materias.keys())
extensiones = config["file_extensions"]
detectar_limpiables(processed_dir, videos_dir, codigos_validos, extensiones)