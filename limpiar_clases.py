"""
Detecta videos en processed_videos_path con marker .uploaded
Borrar el mp4 + el .uploaded + el original en videos_dir
Preview interactivo antes de borrar
"""

from pathlib import Path
import re
import sys
import json

# constantes
CONFIG_PATH = Path(__file__).parent / "config.json"
VIDEO_PROCESADO = re.compile(
    r"^(\d{4}-\d{2}-\d{2})_(\d+)([A-Z]{2,4})\.\w+$", re.IGNORECASE
)


# configuracion
def cargar_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"    [ERROR] No se encontró config.json en {CONFIG_PATH}")
        sys.exit(1)
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


# detección de videos que ya fueron subidos y son eliminables
def detectar_limpiables(
    processed_dir: Path,
    videos_dir: Path,
    codigos_validos: set,
) -> list:
    """itera los mp4 en processed_dir que matcheen VIDEO_PROCESADO
    Para cada uno chequea que existe el marker .mp4.uploaded
    Si no existe no es limpiable
    Busca el original en videos_dir con mismo nombre base pero con cualquier extension
    arma un dict por cada grupo con mp4 (Path), uploaded (Path), original (Path o None), fecha, num, codigo
    devuelve una lista ordenada por fecha y código"""
    limpiables = []
    for archivo in processed_dir.iterdir():
        if not archivo.is_file():
            continue
        m = VIDEO_PROCESADO.match(archivo.name)
        if not m:
            continue

        uploaded_marker = archivo.parent / (archivo.name + ".uploaded")
        if not uploaded_marker.exists():
            continue

        fecha, num_str, codigo = m.groups()

        if codigo.upper() not in codigos_validos:
            continue

        nombre_base = f"{fecha}_{num_str}{codigo}"

        originales = [
            f for f in videos_dir.glob(f"{nombre_base}.*") if f.suffix != ".txt"
        ]
        original = originales[0] if originales else None

        limpiables.append(
            {
                "archivo": archivo,
                "original": original,
                "fecha": fecha,
                "num": int(num_str),
                "codigo": codigo,
            }
        )
    limpiables.sort(key=lambda x: (x["fecha"], x["codigo"]))

    return limpiables

# preview interactivo
def mostrar_preview_y_seleccionar(
        limpiables: list[dict],
        config: dict,
) -> list[dict] | None:
    """
    Muestra los videos limpiables, permite elegir cuáles
    saltar, y pide confirmación.
    Devuelve la lista con el campo 'limpiable' asignado, o None si cancela.
    """

    materias = config["materias"]
    print(f"\nCantidad de archivos a eliminar: {len(limpiables)}\n")
    for i, p in enumerate(limpiables, 1):
        nombre_materia = materias.get(p["codigo"], p["codigo"])
        original_info = p['original'].name if p['original'] else "no encontrado"
        print(f"  {i}. {p['archivo'].name}")
        print(f"       Original: {original_info}")
        print(f"       Materia: {nombre_materia}")
        print()
    print("    Saltar eliminación en alguno?")
    try:
        resp = input("    Números separados por coma (Enter para eliminar todos): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    
    skip_indices = set()
    if resp:
        for parte in resp.split(","):
            parte = parte.strip()
            if parte.isdigit():
                idx = int(parte)
                if 1 <= idx <= len(limpiables):
                    skip_indices.add(idx)
    for i, p in enumerate(limpiables, 1):
        p["eliminar"] = i not in skip_indices
    # resumen de confirmación
    print()
    print("    Plan de ejecución:")
    print()
    for i, p in enumerate(limpiables, 1):
        nombre_materia = materias.get(p["codigo"], p["codigo"])
        titulo = f"{nombre_materia} - Clase {p['num']} ({p['fecha']})"
        accion = "eliminar" if p["eliminar"] else "saltar"
        print(f"    {i}. {titulo:50s} -> {accion}")
    print()
    try:
        resp = input("    Está todo correcto?\n    Procedemos con la eliminación? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if resp not in ("s", "si", "y", "yes"):
        return None
    return limpiables

def eliminar_archivos(
        limpiables: list,
) -> None:
    eliminados = 0
    for limpiable in limpiables:

        if not limpiable["eliminar"]:
            continue
        # borrar .uploaded
        uploaded = limpiable["archivo"].parent / (limpiable["archivo"].name + ".uploaded")
        uploaded.unlink()

        # borrar original (si existe)
        if limpiable["original"]:
            limpiable["original"].unlink()
            print(f"    ELIMINADO: {limpiable['original'].name}")

        # borrar .mp4
        limpiable["archivo"].unlink()
        print(f"    ELIMINADO: {limpiable['archivo'].name}")

        eliminados += 1
        
    print()
    if eliminados == 1:
        print(f"Listo. {eliminados} grupo eliminado.")
    else:
        print(f"Listo. {eliminados} grupos eliminados")
    
def procesar(
        config: dict,
) -> None:
    processed_dir = Path(config["processed_videos_path"])
    videos_dir = Path(config["videos_dir"])
    materias = config["materias"]
    codigos_validos = set(materias.keys())

    limpiables = detectar_limpiables(processed_dir, videos_dir, codigos_validos)
    if not limpiables:
        print("No hay videos de clases ya procesadas pendientes de eliminar.")
        print(f"(Criterio: en {processed_dir}, con .mp4.uploaded)")
        return
    
    limpiables = mostrar_preview_y_seleccionar(limpiables, config)
    if limpiables is None:
        print("Abortado.")
        return
    eliminar_archivos(limpiables)
    



# Entrypoint
if __name__ == "__main__":

    config = cargar_config()
    procesar(config)