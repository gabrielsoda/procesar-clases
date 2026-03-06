"""
procesar_clases.py
==================
Detecta videos de clases grabados con OBS en C:\Users\Gabi\Videos que siguen
el patrón YYYY-MM-DD_[N][CODIGO].(mkv|mp4), transcribe los que no tienen .txt
con WhisperX, y genera los archivos .md correspondientes en el vault de Obsidian.

Flujo por cada video pendiente:
  1. Ejecutar WhisperX → genera .txt en la carpeta de videos
  2. Crear [Materia]/Transcripciones/YYYY-MM-DD_[N][COD]_t.md  (texto crudo)
  3. Crear [Materia]/YYYY-MM-DD_[N][COD].md  (frontmatter + texto crudo, estado: cruda)
  4. Detectar clase anterior de la misma materia y actualizar links bidireccionales

Uso:
  uv run procesar_clases.py
  (o desde el alias 'pc' en PowerShell)
"""

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).parent / "config.json"


def cargar_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"[ERROR] No se encontró config.json en {CONFIG_PATH}")
        sys.exit(1)
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Detección de videos pendientes
# ---------------------------------------------------------------------------

VIDEO_PATRON = re.compile(
    r"^(\d{4}-\d{2}-\d{2})_(\d+)([A-Z]{2,3})\.(mkv|mp4)$",
    re.IGNORECASE,
)


def detectar_videos_pendientes(videos_dir: Path, codigos_validos: set, extensiones: list) -> list[dict]:
    """
    Busca videos que:
    - Matchean el patrón YYYY-MM-DD_[N][COD].(mkv|mp4)
    - El código está en codigos_validos
    - No tienen un .txt con el mismo nombre base ya generado
    """
    pendientes = []
    for ext in extensiones:
        for video in videos_dir.glob(f"*.{ext}"):
            m = VIDEO_PATRON.match(video.name)
            if not m:
                continue
            fecha, num_clase, codigo, _ = m.groups()
            codigo = codigo.upper()
            if codigo not in codigos_validos:
                continue
            txt_path = video.with_suffix(".txt")
            if txt_path.exists():
                continue
            pendientes.append({
                "video": video,
                "fecha": fecha,
                "num_clase": num_clase,
                "codigo": codigo,
                "nombre_base": video.stem,  # ej: 2026-02-24_3AA2
            })
    pendientes.sort(key=lambda x: (x["fecha"], x["num_clase"]))
    return pendientes


# ---------------------------------------------------------------------------
# Transcripción con WhisperX
# ---------------------------------------------------------------------------

def transcribir(video_path: Path, whisperx_exe: Path, model: str) -> Path | None:
    """
    Ejecuta WhisperX directamente sobre el video.
    Devuelve la ruta al .txt generado (misma carpeta que el video).
    """
    print(f"\n  Transcribiendo: {video_path.name} ...")
    cmd = [
        str(whisperx_exe),
        str(video_path),
        "--model", model,
        "--output_format", "txt",
        "--output_dir", str(video_path.parent),
    ]
    result = subprocess.run(cmd, capture_output=False, text=True)
    if result.returncode != 0:
        print(f"  [ERROR] WhisperX falló para {video_path.name}")
        return None
    txt_path = video_path.with_suffix(".txt")
    if not txt_path.exists():
        print(f"  [ERROR] No se generó el .txt esperado: {txt_path}")
        return None
    print(f"  Transcripción generada: {txt_path.name}")
    return txt_path


# ---------------------------------------------------------------------------
# Manejo de notas en el vault
# ---------------------------------------------------------------------------

def leer_txt(txt_path: Path) -> str:
    return txt_path.read_text(encoding="utf-8")


def clase_anterior(carpeta_materia: Path, fecha: str, num_clase: str, codigo: str) -> str | None:
    """
    Busca la nota de clase anterior en la carpeta de la materia.
    Ordena por nombre (que empieza con fecha) y devuelve el nombre sin extensión
    de la nota inmediatamente anterior a la actual.
    """
    patron = re.compile(rf"^\d{{4}}-\d{{2}}-\d{{2}}_\d+{codigo}\.md$", re.IGNORECASE)
    notas = sorted(
        [f for f in carpeta_materia.glob("*.md") if patron.match(f.name)],
        key=lambda f: f.name,
    )
    nombre_actual = f"{fecha}_{num_clase}{codigo}.md"
    # Filtramos notas anteriores (por nombre, que incluye fecha)
    anteriores = [n for n in notas if n.name < nombre_actual]
    if anteriores:
        return anteriores[-1].stem  # nombre sin .md
    return None


def actualizar_siguiente_clase(nota_anterior_path: Path, nombre_nueva: str):
    """
    En la nota de la clase anterior, actualiza el campo 'Siguiente clase'
    para que apunte a la nueva nota.
    """
    if not nota_anterior_path.exists():
        return
    contenido = nota_anterior_path.read_text(encoding="utf-8")
    # Reemplaza el valor de "Siguiente clase" en el frontmatter
    nuevo = re.sub(
        r'(Siguiente clase:\s*)"?\[\[.*?\]\]"?',
        f'\\1"[[{nombre_nueva}]]"',
        contenido,
    )
    if nuevo != contenido:
        nota_anterior_path.write_text(nuevo, encoding="utf-8")
        print(f"  Actualizado 'Siguiente clase' en: {nota_anterior_path.name}")


def crear_nota_transcripcion(carpeta_transcripciones: Path, nombre_base: str, texto: str):
    """
    Crea [Materia]/Transcripciones/YYYY-MM-DD_[N][COD]_t.md con solo el texto crudo.
    """
    ruta = carpeta_transcripciones / f"{nombre_base}_t.md"
    ruta.write_text(texto, encoding="utf-8")
    print(f"  Transcripción cruda: {ruta.relative_to(ruta.parent.parent.parent)}")


def crear_nota_clase(
    carpeta_materia: Path,
    nombre_base: str,
    fecha: str,
    num_clase: str,
    codigo: str,
    texto: str,
    anterior: str | None,
    campus: str = "",
    modalidad: str = "",
):
    """
    Crea [Materia]/YYYY-MM-DD_[N][COD].md con frontmatter + texto crudo.
    """
    anterior_link = f'"[[{anterior}]]"' if anterior else '""'
    fecha_legible = datetime.strptime(fecha, "%Y-%m-%d").strftime("%Y-%m-%d")

    frontmatter = f"""---
Campus: {campus}
Modalidad:
  - {modalidad}
Clase anterior: {anterior_link}
Siguiente clase: ""
estado: cruda
tags: []
Aclaración extra: 
---

"""
    ruta = carpeta_materia / f"{nombre_base}.md"
    ruta.write_text(frontmatter + texto, encoding="utf-8")
    print(f"  Nota de clase creada: {ruta.relative_to(carpeta_materia.parent)}")
    return ruta


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

def procesar(config: dict):
    videos_dir = Path(config["videos_dir"])
    vault_dir = Path(config["vault_dir"])
    whisperx_exe = Path(config["whisperx_exe"])
    model = config["whisperx_model"]
    extensiones = config["video_extensions"]
    materias = config["materias"]

    codigos_validos = set(materias.keys())

    if not videos_dir.exists():
        print(f"[ERROR] Carpeta de videos no encontrada: {videos_dir}")
        sys.exit(1)
    if not whisperx_exe.exists():
        print(f"[ERROR] WhisperX no encontrado en: {whisperx_exe}")
        sys.exit(1)

    pendientes = detectar_videos_pendientes(videos_dir, codigos_validos, extensiones)

    if not pendientes:
        print("No hay videos pendientes de transcribir.")
        return

    print(f"\nVideos pendientes encontrados: {len(pendientes)}")
    for p in pendientes:
        print(f"  - {p['video'].name}  →  {materias[p['codigo']]}")

    print("\n" + "=" * 60)

    for p in pendientes:
        video = p["video"]
        fecha = p["fecha"]
        num_clase = p["num_clase"]
        codigo = p["codigo"]
        nombre_base = p["nombre_base"]
        carpeta_materia = vault_dir / materias[codigo]
        carpeta_transcripciones = carpeta_materia / "Transcripciones"

        print(f"\n[{codigo}] Procesando: {video.name}")

        # 1. Transcribir
        txt_path = transcribir(video, whisperx_exe, model)
        if txt_path is None:
            print(f"  [SKIP] Se omite {video.name} por error en transcripción.")
            continue

        # 2. Leer texto
        texto = leer_txt(txt_path)

        # 3. Crear carpeta Transcripciones si no existe
        carpeta_transcripciones.mkdir(parents=True, exist_ok=True)

        # 4. Crear nota _t (texto crudo, sin frontmatter)
        crear_nota_transcripcion(carpeta_transcripciones, nombre_base, texto)

        # 5. Detectar clase anterior
        anterior = clase_anterior(carpeta_materia, fecha, num_clase, codigo)
        if anterior:
            print(f"  Clase anterior detectada: {anterior}")
        else:
            print(f"  No se encontró clase anterior (es la primera de {codigo})")

        # 6. Crear nota de clase con frontmatter
        nota_nueva = crear_nota_clase(
            carpeta_materia=carpeta_materia,
            nombre_base=nombre_base,
            fecha=fecha,
            num_clase=num_clase,
            codigo=codigo,
            texto=texto,
            anterior=anterior,
        )

        # 7. Actualizar "Siguiente clase" en la nota anterior
        if anterior:
            nota_anterior_path = carpeta_materia / f"{anterior}.md"
            actualizar_siguiente_clase(nota_anterior_path, nombre_base)

    print("\n" + "=" * 60)
    print("Procesamiento completado.")


# ---------------------------------------------------------------------------
# Entrada
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    config = cargar_config()
    procesar(config)
