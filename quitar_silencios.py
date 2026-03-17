"""
Toma los videos procesados (ya renombrados con número de clase y con .txt de la transcripción) 
y les quita los silencios con auto-editor

Detecta videos pendientes en videos_dir que:
    - Matcheen el patron YYYY-MM-DD_NCOD.ext  o  YYYY-MM-DD_NCOD_pN.ext
    - No tengan ya un .mp4 en processed_videos_path

Para archivos de audio (sin video), se genera automáticamente un video con
fondo negro a calidad mínima antes de procesar.

Flujo por video:
    1. Recortar silencios con auto-editor → processed_videos_path/YYYY-MM-DD_NCOD.mp4
Uso:
  uv run quitar_silencios.py          # preview interactivo + confirmacion
  uv run quitar_silencios.py -y       # ejecuta el recorte de todos sin pedir confirmacion
"""

from pathlib import Path
import re
import sys
import json
import subprocess
import time
import argparse

# constantes
# path al archivo de configuración (config.json)
CONFIG_PATH = Path(__file__).parent / "config.json"

VIDEO_PROCESADO = re.compile(
    r"^(\d{4}-\d{2}-\d{2})_(\d+)([A-Z]{2,4})\.\w+$",
    re.IGNORECASE,
)
VIDEO_PARTE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})_(\d+)([A-Z]{2,4})_p(\d+)\.\w+$",
    re.IGNORECASE,
)

# configuracion
def cargar_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"    [ERROR] No se encontró config.json en {CONFIG_PATH}")
        sys.exit(1)
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)
    
# utilidad: detección de tipo de archivo
def tiene_video(file_path: Path) -> bool:
    """Detecta si el archivo tiene al menos un stream de video con ffprobe"""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v",
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0",
        str(file_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return "video" in result.stdout

    
# Detección de archivos pendientes
def detectar_pendientes(
        videos_dir: Path,
        processed_dir: Path,
        codigos_validos: set,
        extensiones: list,
) -> list[dict]:
    """
    Busca videos sin .mp4 ya procesado en processed_dir.
    Devuelve lista de dicts con información de cada video, ordenados por fecha y códgio
    """
    pendientes = []
    for ext in extensiones:
        for archivo in videos_dir.glob(f"*.{ext}"):
            m = VIDEO_PROCESADO.match(archivo.name)
            if not m:
                m = VIDEO_PARTE.match(archivo.name)
                if not m:
                    continue
            grupos = m.groups()
            if len(grupos) == 3:
                fecha, num_str, codigo = grupos
                num_parte = None
            else:
                fecha, num_str, codigo, num_parte = grupos
                num_parte = int(num_parte)
            codigo = codigo.upper()
            if codigo not in codigos_validos:
                continue
            #if not archivo.with_suffix(".txt").exists():
            #    continue
            mp4_out = processed_dir / f"{archivo.stem}.mp4"
            if mp4_out.exists():
                continue
            pendientes.append({
                "archivo": archivo,
                "fecha": fecha,
                "num": int(num_str),
                "codigo": codigo,
                "num_parte": num_parte,
                "es_audio": not tiene_video(archivo),
            })
    pendientes.sort(key=lambda x: (x["fecha"], x["codigo"], x["num_parte"] or 0))
    return pendientes


# Convertir de audio a video
def convertir_audio_a_video(audio_path: Path, output_path: Path) -> bool:
    """
    Genera un video con fondo negro y el audio del archivo.
    Calidad mínima 720p, CRF 51, preset ultrafast
    Devuelve True si fue exitosa la transformación
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "color=c=black:s=1280x720:r=1",
        "-i", str(audio_path),
        "-shortest",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "51",
        "-c:a", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ]
    print(f"    Convirtiendo audio a video con fondo negro...")
    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    tiempo = time.time() - t0
    if result.returncode != 0:
        print(f"    [ERROR] Sucedió un error al convertir audio:")
        print(result.stderr[-800:] if result.stderr else "(sin output)")
        return False
    tamanio = output_path.stat().st_size / (1024 * 1024)
    print(f"    Conversión completada en {tiempo:.1f}s — {tamanio:.1f} MB")
    return True




# Preview interactivo

def mostrar_preview_y_seleccionar(
        pendientes:list[dict],
        config: dict,
        auto_yes: bool,
        ) -> list[dict] | None:
    """
    Muestra los archivos pendientes, permite al usuario elegir cuales
    saltar recorte de silencios, y pide confirmación.
    Devuelve una lista con el campo 'trim' asignado, o None si no se elige recortar.
    """
    materias = config["materias"]

    print(f"\nCantidad de archivos pendientes a procesar: {len(pendientes)}\n")

    for i, p in enumerate(pendientes, 1):
        nombre_materia = materias.get(p["codigo"], p["codigo"])
        tipo = "AUDIO" if p["es_audio"] else "VIDEO"
        print(f"  {i}. {p['archivo'].name}")
        print(f"       Materia: {nombre_materia}  [{tipo}]")
        print()

    # selección de archivos a saltar
    if auto_yes:
        for p in pendientes:
            p["trim"] = True
    else:
        print("    Saltar recorte de silencios en alguno?")
        try:
            resp = input("    Números separados por coma (Enter para recortar silencios en todos): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        skip_indices = set()
        if resp:
            for parte in resp.split(","):
                parte = parte.strip()
                if parte.isdigit():
                    idx = int(parte)
                    if 1 <= idx <= len(pendientes):
                        skip_indices.add(idx)
        for i, p in enumerate(pendientes, 1):
            p["trim"] = i not in skip_indices


    # Resumen de confirmación
    print()
    print("    Plan de ejecución:")
    print()
    for i, p in enumerate(pendientes, 1):
        nombre = p["archivo"].name
        if p["es_audio"] and p["trim"]:
            accion = "fondo negro + recorte"
        elif p["es_audio"] and not p["trim"]:
            accion = "fondo negro (sin recorte)"
        elif not p["es_audio"] and p["trim"]:
            accion = "recorte"
        else:
            accion = "sin procesar (usa original)"
        print(f"    {i}. {nombre:40s} -> {accion}")
    print()
    if not auto_yes:
        try:
            resp = input("    Todo está correcto? \n    Continuamos con la ejecución? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if resp not in ("s", "si", "y", "yes"):
            return None
    return pendientes

# recorte de silencios con auto-editor

def recortar_silencios(
        video_path: Path,
        output_path: Path,
        config: dict,
) -> bool:
    """
    Recorta los silencios del video usando auto-editor
    Usa Smart Cut, solo re-encodea los frames en los puntos de corte
    Rápido y sin pérdida de calidad.
    Devuelve True si el proceso fue exitoso
    """
    auto_editor_exe = Path(__file__).parent / config.get(
        "auto_editor_exe", r"bin\auto-editor.exe"
    )

    if not auto_editor_exe.exists():
        print(f"    [ERROR] No se encontró el ejecutable de auto-editor en: {auto_editor_exe}. \n    Revisar si config.json es correcto")
        return False
    
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(auto_editor_exe),
        str(video_path),
        "--margin", "0s",
        "--no-open",
        "-o", str(output_path),
    ]

    print(f"    Recortando silencios...")
    t0 = time.time()
    result = subprocess.run(cmd)
    tiempo = time.time() - t0

    if result.returncode != 0:
        print(f"    [ERROR] auto-editor falló ({result.returncode}):")
        return False
    
    if not output_path.exists():
        print(f"    [ERROR] auto-editor no generó el archivo de salida")
        return False
    
    tamanio = output_path.stat().st_size / (1024 * 1024)
    print(f"    Recorte completado en {tiempo:.1f}s — {tamanio:.1f} MB")
    return True    


# flujo principal

def procesar(config: dict, auto_yes: bool = False):
    videos_dir = Path(config["videos_dir"])
    processed_dir = Path(config["processed_videos_path"])
    materias = config["materias"]
    extensiones = config["file_extensions"]
    codigos_validos = set(materias.keys())
    if not videos_dir.exists():
        print(f"[ERROR] Carpeta de videos no encontrada: {videos_dir}")
        sys.exit(1)
    pendientes = detectar_pendientes(
        videos_dir, processed_dir, codigos_validos, extensiones
    )
    if not pendientes:
        print("No hay archivos pendientes de procesar.")
        print(f"(Criterio: en {videos_dir}, sin .mp4 en {processed_dir})")
        return
    pendientes = mostrar_preview_y_seleccionar(pendientes, config, auto_yes)
    if pendientes is None:
        print("Abortado.")
        return
    print()
    for p in pendientes:
        archivo = p["archivo"]
        stem = archivo.stem
        mp4_path = processed_dir / f"{stem}.mp4"
        nombre_materia = materias.get(p["codigo"], p["codigo"])
        print(f"-- {nombre_materia} — {stem} --")
        # Caso1: video sin procesar (no trim, no audio)
        if not p["es_audio"] and not p["trim"]:
            print(f"  Sin procesar. Usar original: {archivo.name}")
            print()
            continue
        # Caso2: audio sin recorte → solo fondo negro
        if p["es_audio"] and not p["trim"]:
            ok = convertir_audio_a_video(archivo, mp4_path)
            if not ok:
                print(f"  [SKIP] Error en la conversion.")
            print()
            continue
        # Caso3: audio con recorte → fondo negro + auto-editor
        if p["es_audio"] and p["trim"]:
            temp_video = processed_dir / f"{stem}_temp.mp4"
            ok = convertir_audio_a_video(archivo, temp_video)
            if not ok:
                print(f"  [SKIP] Error en la conversion.")
                print()
                continue
            ok = recortar_silencios(temp_video, mp4_path, config)
            temp_video.unlink(missing_ok=True)
            if not ok:
                print(f"  [SKIP] Error en el recorte.")
            print()
            continue
        # Caso4: video con recorte → auto-editor directo
        ok = recortar_silencios(archivo, mp4_path, config)
        if not ok:
            print(f"  [SKIP] Error en el recorte.")
        print()
    print("Listo.")



# Entrypoint
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Recorta silencios de videos de clases con auto-editor.",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Recortar todos los archivos sin pedir confirmación",
    )
    args = parser.parse_args()
    config = cargar_config()
    procesar(config, auto_yes=args.yes)