"""
sube videos en 'processed_videos_path' a Youtube

Detecta videos pendientes en processed_videos_path
que matcheen el patron y no tengo un .uploaded marker

Se suben como Privados

Flujo:
    1. Subir video con título Materia - Clase N (YYYY-MM-DD)
    2. Agregar a playlist según código de la materia
    3. crea uploaded marker

uso: uv run subir_clases.py     # Preview interactivo
        "" -y                   # sube todo sin pedir confirmación

"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# constantes
CONFIG_PATH = Path(__file__).parent / "config.json"
SCOPES = ["https://www.googleapis.com/auth/youtube"]
TOKEN_PATH = Path(__file__).parent / "credentials" / "youtube_token.json"
VIDEO_PROCESADO = re.compile(
    r"^(\d{4}-\d{2}-\d{2})_(\d+)([A-Z0-9]{2,4})\.\w+$",
    re.IGNORECASE,
)
VIDEO_OTRO = re.compile(
    r"^(\d{4}-\d{2}-\d{2})_(\d+)_(.+)\.\w+$",
)


# configuracion
def cargar_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"    [ERROR] No se encontró config.json en {CONFIG_PATH}")
        sys.exit(1)
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


# autenticación
def autenticar_youtube(config: dict):
    """
    Autentica con la YouTube Data API v3 via OAuth 2.0.
    La primera vez abre el navegador para autorizar el acceso.
    Las veces siguientes usa el token guardado en credentials/youtube_token.json.
    Devuelve el objeto de servicio de YouTube autenticado.
    """

    creds = None
    # cargar token guardado si existe
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    # si no hay token o está vencido, obtener uno nuevo
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("    Refrescando token de acceso...")
            try:
                creds.refresh(Request())
            except Exception:
                print("    Token expirado o revocado. Re-autenticando...")
                TOKEN_PATH.unlink(missing_ok=True)
                client_secret_path = CONFIG_PATH.parent / config["youtube_credentials"]
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(client_secret_path), SCOPES
                )
                creds = flow.run_local_server(port=0)
        else:
            print("    Abriendo navegador para autenticar con Google...")
            client_secret_path = CONFIG_PATH.parent / config["youtube_credentials"]
            if not client_secret_path.exists():
                print(f"    [ERROR] No se encontró {client_secret_path}")
                print("    Descargá el client_secret.json desde Google Cloud Console")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(
                str(client_secret_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
        # guardar token para la próxima vez
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        print("    Token guardado en credentials/youtube_token.json")
    youtube = build("youtube", "v3", credentials=creds)
    return youtube


# detección de pendientes
def detectar_pendientes(
    processed_dir: Path,
    codigos_validos: set,
) -> list[dict]:
    """
    Busca videos en processed_dir sin .uploaded marker.
    Devuelve lista de dicts con información de cada video, ordenados por fecha y código.
    """
    pendientes = []
    for archivo in processed_dir.iterdir():
        if not archivo.is_file():
            continue
        uploaded_marker = archivo.parent / (archivo.name + ".uploaded")
        if uploaded_marker.exists():
            continue

        m = VIDEO_PROCESADO.match(archivo.name)
        if m:
            fecha, num_str, codigo = m.groups()
            codigo = codigo.upper()
            if codigo not in codigos_validos:
                continue
            pendientes.append(
                {
                    "archivo": archivo,
                    "fecha": fecha,
                    "num": int(num_str),
                    "codigo": codigo,
                }
            )
            continue

        m_otro = VIDEO_OTRO.match(archivo.name)
        if m_otro:
            fecha, num_str, nombre_original = m_otro.groups()
            pendientes.append(
                {
                    "archivo": archivo,
                    "fecha": fecha,
                    "num": int(num_str),
                    "codigo": None,
                    "nombre_original": nombre_original,
                }
            )

    pendientes.sort(key=lambda x: (x["fecha"], x.get("codigo") or ""))
    return pendientes


# preview interactivo
def mostrar_preview_y_seleccionar(
    pendientes: list[dict],
    config: dict,
    auto_yes: bool,
) -> list[dict] | None:
    """
    Muestra los videos pendientes de subir, permite elegir cuáles
    saltar, y pide confirmación.
    Devuelve la lista con el campo 'subir' asignado, o None si cancela.
    """

    materias = config["materias"]
    playlists = config.get("youtube_playlists", {})
    otros_playlist = config.get("otros_playlist", "")
    print(f"\nCantidad de videos pendientes de subir: {len(pendientes)}\n")
    for i, p in enumerate(pendientes, 1):
        if p["codigo"] is not None:
            nombre_materia = materias.get(p["codigo"], p["codigo"])
            titulo = f"{nombre_materia} - Clase {p['num']} ({p['fecha']})"
            playlist_id = playlists.get(p["codigo"], "")
        else:
            titulo = f"{p['nombre_original']} ({p['fecha']})"
            playlist_id = otros_playlist
        playlist_info = "sí" if playlist_id else "no configurada"
        print(f"  {i}. {p['archivo'].name}")
        print(f"       Título: {titulo}")
        print(f"       Playlist: {playlist_info}")
        print()
    if auto_yes:
        for p in pendientes:
            p["subir"] = True
    else:
        print("    Saltar subida en alguno?")
        try:
            resp = input(
                "    Números separados por coma (Enter para subir todos): "
            ).strip()
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
            p["subir"] = i not in skip_indices
    # resumen de confirmación
    print()
    print("    Plan de ejecución:")
    print()
    for i, p in enumerate(pendientes, 1):
        if p["codigo"] is not None:
            nombre_materia = materias.get(p["codigo"], p["codigo"])
            titulo = f"{nombre_materia} - Clase {p['num']} ({p['fecha']})"
        else:
            titulo = f"{p['nombre_original']} ({p['fecha']})"
        accion = "subir" if p["subir"] else "saltar"
        print(f"    {i}. {titulo:50s} -> {accion}")
    print()
    if not auto_yes:
        try:
            resp = (
                input("    Está todo correcto?\n    Continuamos con la subida? [y/N]: ")
                .strip()
                .lower()
            )
        except (EOFError, KeyboardInterrupt):
            print()
            return None
        if resp not in ("s", "si", "y", "yes"):
            return None
    return pendientes


# subida de video
def subir_video(youtube, video_path: Path, titulo: str) -> str | None:
    """
    Sube un video a Youtube
    Usa resumable upload con reintentos y exponential backoff.
    Devuelve el video_id si fue exitoso, None si falló.
    """
    body = {
        "snippet": {
            "title": titulo,
            "description": "",
            "categoryId": "27",
            "defaultLanguage": "es-419",
        },
        "status": {
            "privacyStatus": "private",
        },
    }
    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=256 * 1024 * 1024,
    )
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )
    print("    Subiendo video...")
    response = None
    intentos = 0
    max_intentos = 5
    t0 = time.time()
    while response is None:
        try:
            status, response = request.next_chunk()
            if status:
                porcentaje = int(status.progress() * 100)
                print(f"    Progreso: {porcentaje}%")
        except HttpError as e:
            if e.resp.status in [500, 502, 503, 504] and intentos < max_intentos:
                intentos += 1
                espera = 2**intentos
                print(
                    f"    Error del servidor, reintentando en {espera}s... (intento {intentos}/{max_intentos})"
                )
                time.sleep(espera)
            else:
                print(f"    [ERROR] Error al subir video: {e}")
                return None
    tiempo = time.time() - t0
    video_id = response["id"]
    tamanio = video_path.stat().st_size / (1024 * 1024)
    print(f"    Subido en {tiempo:.1f}s — {tamanio:.1f} MB — ID: {video_id}")
    return video_id


# asignación a playlist
def agregar_a_playlist(youtube, video_id: str, playlist_id: str) -> bool:
    """
    Agrega un video a una playlist de YouTube.
    Devuelve True si fue exitoso, False si falló.
    """
    body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {
                "kind": "youtube#video",
                "videoId": video_id,
            },
        },
    }
    try:
        youtube.playlistItems().insert(
            part="snippet",
            body=body,
        ).execute()
        print(f"    Agregado a playlist {playlist_id}")
        return True
    except HttpError as e:
        print(f"    [ERROR] Error al agregar a playlist: {e}")
        return False


# flujo principal
def procesar(config: dict, auto_yes: bool = False):
    processed_dir = Path(config["processed_videos_path"])
    materias = config["materias"]
    playlists = config.get("youtube_playlists", {})
    otros_playlist = config.get("otros_playlist", "")
    codigos_validos = set(materias.keys())
    if not processed_dir.exists():
        print(f"[ERROR] Carpeta de videos no encontrada: {processed_dir}")
        sys.exit(1)
    pendientes = detectar_pendientes(processed_dir, codigos_validos)
    if not pendientes:
        print("No hay videos pendientes de subir.")
        print(f"(Criterio: en {processed_dir}, sin .mp4.uploaded)")
        return
    pendientes = mostrar_preview_y_seleccionar(pendientes, config, auto_yes)
    if pendientes is None:
        print("Abortado.")
        return
    youtube = autenticar_youtube(config)
    print()
    subidos = 0
    errores = 0
    for p in pendientes:
        if not p["subir"]:
            continue
        archivo = p["archivo"]
        if p["codigo"] is not None:
            nombre_materia = materias.get(p["codigo"], p["codigo"])
            titulo = f"{nombre_materia} - Clase {p['num']} ({p['fecha']})"
            playlist_id = playlists.get(p["codigo"], "")
        else:
            titulo = f"{p['nombre_original']} ({p['fecha']})"
            playlist_id = otros_playlist
        print(f"-- {titulo} --")
        # subir video
        video_id = subir_video(youtube, archivo, titulo)
        if not video_id:
            print("    [SKIP] Error en la subida.")
            errores += 1
            print()
            continue
        # agregar a playlist si está configurada
        if playlist_id:
            agregar_a_playlist(youtube, video_id, playlist_id)
        # crear marker de subido
        uploaded_marker = archivo.parent / (archivo.name + ".uploaded")
        uploaded_marker.touch()
        print(f"    Marker creado: {uploaded_marker.name}")
        subidos += 1
        print()
    # resumen final
    print(f"Listo. {subidos} video(s) subido(s).", end="")
    if errores:
        print(f" {errores} error(es).", end="")
    print()


# entrypoint
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Sube videos de clases procesados a YouTube.",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Subir todos los archivos sin pedir confirmación",
    )
    args = parser.parse_args()
    config = cargar_config()
    procesar(config, auto_yes=args.yes)
