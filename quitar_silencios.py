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
import shutil
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
            ya_procesado = any(processed_dir.glob(f"{clave}.*"))
            if ya_procesado:
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


def copiar_sin_recortar(input_path: Path, output_path: Path) -> bool:
    """Copia el archivo a processed_dir sin modificar. Devuelve True si fue exitoso."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"    Copiando sin recortar...")
    try:
        shutil.copy2(str(input_path), str(output_path))
    except OSError as e:
        print(f"    [ERROR] Error al copiar: {e}")
        return False
    tamanio = output_path.stat().st_size / (1024 * 1024)
    print(f"    Copiado — {tamanio:.1f} MB")
    return True


# Preview interactivo
def mostrar_preview_y_seleccionar(
        grupos: list[dict],
        config: dict,
        auto_yes: bool,
) -> list[dict] | None:
    """
    Muestra los archivos pendientes con acción por defecto,
    permite al usuario cambiar acciones individuales, y pide confirmación.
    Devuelve la lista de grupos con el campo 'accion' asignado, o None si cancela.
    """
    materias = config["materias"]

    # Asignar acción por defecto
    for g in grupos:
        tiene_audio = any(a["es_audio"] for a in g["archivos"])
        g["accion"] = "copiar" if tiene_audio else "recortar"

    print(f"\nArchivos pendientes a procesar: {len(grupos)}\n")

    for i, g in enumerate(grupos, 1):
        nombre_materia = materias.get(g["codigo"], g["codigo"])
        principal = g["archivos"][0]["archivo"].name
        tiene_audio = any(a["es_audio"] for a in g["archivos"])
        tipo = "AUDIO" if tiene_audio else "VIDEO"

        if g["es_multipart"]:
            partes_extra = ", ".join(a["archivo"].name for a in g["archivos"][1:])
            print(f"  {i}. {principal}  (+ {partes_extra})")
        else:
            print(f"  {i}. {principal}")

        accion_texto = _texto_accion(g)
        print(f"       {nombre_materia}  [{tipo}]  →  {accion_texto}")
        print()

    # Selección de cambios
    if not auto_yes:
        print("  ¿Cambiar acción en alguno?")
        try:
            resp = input("  Números separados por coma (Enter para continuar): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None

        if resp:
            indices_cambiar = set()
            for parte in resp.split(","):
                parte = parte.strip()
                if parte.isdigit():
                    idx = int(parte)
                    if 1 <= idx <= len(grupos):
                        indices_cambiar.add(idx)

            for idx in sorted(indices_cambiar):
                g = grupos[idx - 1]
                tiene_audio = any(a["es_audio"] for a in g["archivos"])
                nombre = g["archivos"][0]["archivo"].name
                print()
                if tiene_audio:
                    print(f"  {idx}. {nombre} [AUDIO]:")
                    print(f"     a) convertir + recortar   b) copiar sin recortar   c) saltear")
                    default = "b"
                else:
                    print(f"  {idx}. {nombre} [VIDEO]:")
                    print(f"     a) recortar silencios   b) copiar sin recortar   c) saltear")
                    default = "a"

                try:
                    eleccion = input(f"     [{default}]: ").strip().lower() or default
                except (EOFError, KeyboardInterrupt):
                    print()
                    return None

                if tiene_audio:
                    opciones = {"a": "convertir_recortar", "b": "copiar", "c": "saltear"}
                else:
                    opciones = {"a": "recortar", "b": "copiar", "c": "saltear"}
                g["accion"] = opciones.get(eleccion, opciones[default])

    # Plan de ejecución
    print()
    print("  Plan de ejecución:")
    print()
    for i, g in enumerate(grupos, 1):
        if g["es_multipart"]:
            nombre = g["clave"] + "  (multipart)"
        else:
            nombre = g["archivos"][0]["archivo"].name
        accion_texto = _texto_accion(g)
        print(f"    {i}. {nombre:40s} →  {accion_texto}")
    print()

    if not auto_yes:
        try:
            resp = input("  Continuamos con la ejecución? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if resp not in ("s", "si", "y", "yes"):
            return None

    return grupos


def _texto_accion(g: dict) -> str:
    """Devuelve el texto descriptivo de la acción asignada a un grupo."""
    accion = g["accion"]
    sufijo = " + concatenar" if g["es_multipart"] else ""
    textos = {
        "recortar": "recortar silencios",
        "copiar": "copiar sin recortar",
        "convertir_recortar": "convertir a video + recortar",
        "saltear": "saltear",
    }
    return textos.get(accion, str(accion)) + sufijo

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
    lista_path: Path | None = None
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
    if lista_path is not None:
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
        archivo_final = processed_dir / f"{g['clave']}{g['archivos'][0]['archivo'].suffix}"
        print(f"-- {nombre_materia} — {g['clave']} --")
        accion = g["accion"]

        # saltear
        if accion == "saltear":
            print(f"    Salteado.")
            print()
            continue

        # grupo de un solo archivo
        if not g["es_multipart"]:
            a = g["archivos"][0]
            archivo = a["archivo"]

            if accion == "copiar":
                if a["es_audio"]:
                    ok = convertir_audio_a_video(archivo, archivo_final)
                else:
                    ok = copiar_sin_recortar(archivo, archivo_final)
                if not ok:
                    print(f"    [SKIP] Error al copiar.")
                print()
                continue

            if accion == "recortar":
                ok = recortar_silencios(archivo, archivo_final, config)
                if not ok:
                    print(f"    [SKIP] Error en el recorte.")
                print()
                continue

            if accion == "convertir_recortar":
                temp_video = processed_dir / f"{g['clave']}_temp.mp4"
                ok = convertir_audio_a_video(archivo, temp_video)
                if not ok:
                    print(f"    [SKIP] Error en la conversión.")
                    print()
                    continue
                ok = recortar_silencios(temp_video, archivo_final, config)
                temp_video.unlink(missing_ok=True)
                if not ok:
                    print(f"    [SKIP] Error en el recorte.")
                print()
                continue

        # grupo multipart
        partes_procesadas = []
        error = False
        for a in g["archivos"]:
            archivo = a["archivo"]
            num_p = a["num_parte"] or 1

            if accion == "copiar":
                if a["es_audio"]:
                    temp = processed_dir / f"{g['clave']}_p{num_p}.mp4"
                    ok = convertir_audio_a_video(archivo, temp)
                    if not ok:
                        print(f"    [SKIP] Error en la conversión de {archivo.name}")
                        error = True
                        break
                    partes_procesadas.append(temp)
                else:
                    partes_procesadas.append(archivo)
            else:
                # recortar o convertir_recortar
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
                partes_procesadas.append(temp_recortado)

        if not error:
            ok = concatenar_partes(partes_procesadas, archivo_final)
            if not ok:
                print(f"    [SKIP] Error al concatenar.")
        # limpiar temporales
        for temp in partes_procesadas:
            if temp.parent == processed_dir:
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