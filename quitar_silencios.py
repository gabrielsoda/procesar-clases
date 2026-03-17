"""
Toma los videos procesados (ya renombrados con número de clase) y les quita los silencios con auto-editor

Detecta videos pendientes en videos_dir que:
    - Matcheen el patron YYYY-MM-DD_NCOD.ext o YYYY-MM-DD_NCOD_pN.ext
    - No tengan ya un .mp4 en processed_videos_path
Para archivos de audio (sin video), se genera automáticamente un video con
fondo negro a calidad mínima antes de procesar.
Cuando hay partes (_p2, _p3...) se agrupan, procesan individualmente y concatenan en un único .mp4 final.

Flujo por grupo:
    1. Recortar silencios de cada archivo con auto-editor
    2. Si es multipart, concatenar las partes en un solo .mp4
    → processed_videos_path/YYYY-MM-DD_NCOD.mp4
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

# Obtener codecs, se utiliza para no re-encodear si no es neceario
def obtener_codecs(file_path: Path) -> tuple[str, str]:
    """Devuelve (codec_video, codec_audio) del archivo"""
    # codec de video
    cmd_v = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name",
        "-of", "csv=p=0",
        str(file_path),
    ]
    # codec de audio
    cmd_a = [
        "ffprobe", "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name",
        "-of", "csv=p=0",
        str(file_path),
    ]
    video = subprocess.run(cmd_v, capture_output=True, text=True).stdout.strip()
    audio = subprocess.run(cmd_a, capture_output=True, text=True).stdout.strip()
    return (video, audio)


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
            clave = f"{fecha}_{num_str}{codigo}"
            mp4_out = processed_dir / f"{clave}.mp4"
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

# agrupación de partes
def agrupar_partes_pendientes(pendientes:list[dict]) -> list[dict]:
    """
    Agrupa archivos que comparten YYYY-MM-DD_NCOD en un solo grupo siendo
    el principal sin _pN y sus partes con _pN. Devuelve lista de grupos 
    ordenados por fecha y código
    """ 
    grupos_dict = {}
    for p in pendientes:
        clave = f"{p['fecha']}_{p['num']}{p['codigo']}"
        if clave not in grupos_dict:
            grupos_dict[clave] = {
                "clave": clave,
                "fecha": p["fecha"],
                "num": p["num"],
                "codigo":p["codigo"],
                "archivos": [],
            }
        grupos_dict[clave]["archivos"].append({
            "archivo": p["archivo"],
            "num_parte": p["num_parte"],
            "es_audio": p["es_audio"],
        })
    grupos = list(grupos_dict.values())
    for g in grupos:
        g["archivos"].sort(key=lambda a: a["num_parte"] or 0)
        g["es_multipart"] = len(g["archivos"]) > 1
    grupos.sort(key=lambda g: (g["fecha"], g["codigo"]))
    return grupos


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
        grupos:list[dict],
        config: dict,
        auto_yes: bool,
        ) -> list[dict] | None:
    """
    Muestra los archivos pendientes, permite al usuario elegir cuales
    saltar recorte de silencios, y pide confirmación.
    Devuelve una lista de grupos con el campo 'trim' asignado, o None si no se eligió recortar.
    """
    materias = config["materias"]

    print(f"\nCantidad de grupos de archivos pendientes a procesar: {len(grupos)}\n")

    for i, g in enumerate(grupos, 1):
        nombre_materia = materias.get(g["codigo"], g["codigo"])
        principal = g["archivos"][0]["archivo"].name
        if g["es_multipart"]:
            partes_extra = ", ".join(a["archivo"].name for a in g["archivos"][1:])
            print(f"  {i}. {principal}  (+ {partes_extra})")
        else:
            print(f"  {i}. {principal}")
        tiene_audio = any(a["es_audio"] for a in g["archivos"])
        tipo = "AUDIO" if tiene_audio else "VIDEO"
        print(f"       Materia: {nombre_materia}  [{tipo}]")
        print()

    # selección de archivos a saltar
    if auto_yes:
        for g in grupos:
            g["trim"] = True
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
                    if 1 <= idx <= len(grupos):
                        skip_indices.add(idx)
        for i, g in enumerate(grupos, 1):
            g["trim"] = i not in skip_indices


    # Resumen de confirmación
    print()
    print("    Plan de ejecución:")
    print()
    for i, g in enumerate(grupos, 1):
        tiene_audio = any(a["es_audio"] for a in g["archivos"])
        if g["es_multipart"]:
            nombre = g["clave"] + "  (multipart)"
        else:
            nombre = g["archivos"][0]["archivo"].name
        if tiene_audio and g["trim"]:
            accion = "fondo negro + recorte"
        elif tiene_audio and not g["trim"]:
            accion = "fondo negro (sin recorte)"
        elif not tiene_audio and g["trim"]:
            accion = "recorte"
        else:
            accion = "sin procesar (usa original)"
        if g["es_multipart"]:
            accion += " + concatenar"
        print(f"    {i}. {nombre:40s} -> {accion}")
    print()
    if not auto_yes:
        try:
            resp = input("    Está todo correcto? \n    Continuamos con la ejecución? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if resp not in ("s", "si", "y", "yes"):
            return None
    return grupos

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




# Concatenación de partes
def concatenar_partes(partes: list[Path], output: Path) -> bool:
    """
    Concatena múltiples archivos de video en uno solo.
    Detecta automáticamente si los codecs son iguales para evitar re-encode.
    Devuelve True si fue exitoso.
    """
    output.parent.mkdir(parents=True, exist_ok=True)
    codecs = [obtener_codecs(p) for p in partes]
    stream_copy = len(set(codecs)) == 1
    if stream_copy:
        print(f"    Mismos codecs, concatenando sin re-encode...")
        lista_path = output.with_suffix(".txt")
        contenido = "\n".join(f"file '{p}'" for p in partes)
        lista_path.write_text(contenido, encoding="utf-8")
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(lista_path),
            "-c", "copy",
            str(output),
        ]
    else:
        print(f"    Codecs distintos detectados, concatenando con re-encode...")
        # concat filter
        cmd = ["ffmpeg", "-y"]
        for p in partes:
            cmd += ["-i", str(p)]
        n = len(partes)
        filtro = "".join(f"[{i}:v][{i}:a]" for i in range(n))
        filtro += f"concat=n={n}:v=1:a=1[v][a]"
        cmd += [
            "-filter_complex", filtro,
            "-map", "[v]",
            "-map", "[a]",
            str(output),
        ]
    print(f"    Concatenando {len(partes)} partes...")
    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    tiempo = time.time() - t0
    # limpiar archivo de lista temporal
    if stream_copy:
        lista_path.unlink(missing_ok=True)
    if result.returncode != 0:
        print(f"    [ERROR] Error al concatenar:")
        print(result.stderr[-800:] if result.stderr else "(sin output)")
        return False
    tamanio = output.stat().st_size / (1024 * 1024)
    print(f"    Concatenación completada en {tiempo:.1f}s — {tamanio:.1f} MB")
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
        print("No hay archivos pendientes para procesar.")
        print(f"(Criterio: en {videos_dir}, sin .mp4 en {processed_dir})")
        return
    grupos = agrupar_partes_pendientes(pendientes)
    grupos = mostrar_preview_y_seleccionar(grupos, config, auto_yes)
    if grupos is None:
        print("Abortado.")
        return
    print()
    for g in grupos:
        nombre_materia = materias.get(g["codigo"], g["codigo"])
        mp4_final = processed_dir / f"{g['clave']}.mp4"
        print(f"-- {nombre_materia} — {g['clave']} --")
        # grupo de un solo archivo
        if not g["es_multipart"]:
            a = g["archivos"][0]
            archivo = a["archivo"]
            if not a["es_audio"] and not g["trim"]:
                print(f"    Sin procesar. Usar original: {archivo.name}")
                print()
                continue
            if a["es_audio"] and not g["trim"]:
                ok = convertir_audio_a_video(archivo, mp4_final)
                if not ok:
                    print(f"    [SKIP] Error en la conversión.")
                print()
                continue
            if a["es_audio"] and g["trim"]:
                temp_video = processed_dir / f"{g['clave']}_temp.mp4"
                ok = convertir_audio_a_video(archivo, temp_video)
                if not ok:
                    print(f"    [SKIP] Error en la conversión.")
                    print()
                    continue
                ok = recortar_silencios(temp_video, mp4_final, config)
                temp_video.unlink(missing_ok=True)
                if not ok:
                    print(f"    [SKIP] Error en el recorte.")
                print()
                continue
            ok = recortar_silencios(archivo, mp4_final, config)
            if not ok:
                print(f"    [SKIP] Error en el recorte.")
            print()
            continue
        # grupo multipart sin recorte → concatenar originales con re-encode
        if not g["trim"]:
            partes_preparadas = []
            error = False
            for a in g["archivos"]:
                if a["es_audio"]:
                    temp = processed_dir / f"{a['archivo'].stem}_temp.mp4"
                    ok = convertir_audio_a_video(a["archivo"], temp)
                    if not ok:
                        print(f"    [SKIP] Error en la conversión de {a['archivo'].name}")
                        error = True
                        break
                    partes_preparadas.append(temp)
                else:
                    partes_preparadas.append(a["archivo"])
            if not error:
                ok = concatenar_partes(partes_preparadas, mp4_final)
                if not ok:
                    print(f"    [SKIP] Error al concatenar.")
            for temp in partes_preparadas:
                if temp.parent == processed_dir:
                    temp.unlink(missing_ok=True)
            print()
            continue
        # grupo multipart con recorte → recortar cada parte + concatenar con copy
        partes_recortadas = []
        error = False
        for a in g["archivos"]:
            archivo = a["archivo"]
            num_p = a["num_parte"] or 1
            temp_recortado = processed_dir / f"{g['clave']}_trimmed_p{num_p}.mp4"
            if a["es_audio"]:
                temp_video = processed_dir / f"{archivo.stem}_temp.mp4"
                ok = convertir_audio_a_video(archivo, temp_video)
                if not ok:
                    print(f"    [SKIP] Error en la conversión de {archivo.name}")
                    error = True
                    break
                ok = recortar_silencios(temp_video, temp_recortado, config)
                temp_video.unlink(missing_ok=True)
            else:
                ok = recortar_silencios(archivo, temp_recortado, config)
            if not ok:
                print(f"    [SKIP] Error en el recorte de {archivo.name}")
                error = True
                break
            partes_recortadas.append(temp_recortado)
        if not error:
            ok = concatenar_partes(partes_recortadas, mp4_final)
            if not ok:
                print(f"    [SKIP] Error al concatenar.")
        for temp in partes_recortadas:
            temp.unlink(missing_ok=True)
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