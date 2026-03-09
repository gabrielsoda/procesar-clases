"""
procesar_clases.py
==================
Detecta videos de clases grabados con OBS en el directorio configurado,
transcribe los que no tienen .txt con WhisperX, y genera los archivos .md
correspondientes en el vault de Obsidian.

Convención de nombres de video (renombrado manual por el usuario):

  Principal : YYYY-MM-DD_CODIGO.(mkv|mp4|m4a)
  Parte     : YYYY-MM-DD_CODIGO_pN.(mkv|mp4|m4a)   (N = 2, 3, …)

El número de clase (N) se calcula automáticamente leyendo las notas
existentes en la carpeta de la materia dentro del vault.

Flujo por cada video pendiente:
  1. Preview: mostrar qué se va a hacer y pedir confirmación (salvo -y)
  2. Calcular número de clase leyendo vault
  3. Renombrar video: YYYY-MM-DD_COD → YYYY-MM-DD_NCOD
  4. Ejecutar WhisperX → genera .txt en la carpeta de videos
  5. Crear [Materia]/Transcripciones/YYYY-MM-DD_NCOD_t.md  (texto crudo)
  6. Crear [Materia]/YYYY-MM-DD_NCOD.md  (frontmatter del template + texto)
  7. Detectar clase anterior y actualizar links bidireccionales

Para partes (_p2, _p3…):
  - Transcribe y appendea el texto a la nota principal existente
  - No crea nota nueva ni actualiza links

El frontmatter de cada nota se toma del template correspondiente en
Templates/Clase de {CODIGO}.md dentro del vault. Si no existe el template,
se usa un frontmatter genérico como fallback.

Uso:
  uv run procesar_clases.py         # preview + confirmación
  uv run procesar_clases.py -y      # ejecuta sin pedir confirmación
  (o desde el alias 'pc' / 'pc -y' en PowerShell)
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


# ─── Configuración ───────────────────────────────────────────────────────────

CONFIG_PATH = Path(__file__).parent / "config.json"


def cargar_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"[ERROR] No se encontró config.json en {CONFIG_PATH}")
        sys.exit(1)
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


# ─── Lectura y procesamiento de templates de Obsidian ────────────────────────


def leer_template_frontmatter(vault_dir: Path, codigo: str) -> str | None:
    """
    Lee el archivo Templates/Clase de {CODIGO}.md del vault y extrae
    el bloque YAML entre los delimitadores ---.
    Devuelve el bloque completo como string (incluyendo los ---),
    o None si el template no existe o no tiene frontmatter válido.
    """
    template_path = vault_dir / "Templates" / f"Clase de {codigo}.md"
    if not template_path.exists():
        print(f"  [AVISO] No se encontró template para {codigo}: {template_path}")
        return None

    contenido = template_path.read_text(encoding="utf-8")

    # Extrae todo lo que hay entre el primer --- y el segundo ---
    m = re.match(r"^(---\n.*?---)", contenido, re.DOTALL)
    if not m:
        print(f"  [AVISO] El template {template_path.name} no tiene frontmatter válido")
        return None

    return m.group(1)


def aplicar_valores_al_frontmatter(
    frontmatter: str, anterior: str | None, fecha: str = ""
) -> str:
    """
    Toma el bloque YAML del template y reemplaza los campos dinámicos:
    - 'Clase anterior' → link a la clase anterior real (o vacío si es la primera)
    - 'Siguiente clase' → siempre vacío al crear (se llena cuando llegue la siguiente)
    - 'estado'         → siempre 'cruda' al crear
    - 'fecha'          → fecha real extraída del nombre del video (si el campo existe)

    Los tokens {{date:...}} que Obsidian inserta en los links de navegación
    son descartados porque el script calcula los valores reales.
    """
    resultado = frontmatter

    anterior_valor = f'"[[{anterior}]]"' if anterior else '""'

    resultado = re.sub(
        r"(Clase anterior:\s*).*",
        rf"\1{anterior_valor}",
        resultado,
    )
    resultado = re.sub(
        r"(Siguiente clase:\s*).*",
        r'\1""',
        resultado,
    )
    # Asegura estado: cruda aunque el template tenga otro valor
    resultado = re.sub(
        r"(estado:\s*).*",
        r"\1cruda",
        resultado,
    )
    # Reemplaza fecha: si existe en el template (usado en OTR y eventualmente otros)
    if fecha:
        resultado = re.sub(
            r"(fecha:\s*).*",
            rf"\1{fecha}",
            resultado,
        )

    return resultado


def frontmatter_generico(anterior: str | None) -> str:
    """
    Frontmatter de fallback usado cuando no existe template para el código.
    """
    anterior_valor = f'"[[{anterior}]]"' if anterior else '""'
    return f"""---
Campus: 
Modalidad:
  - 
Clase anterior: {anterior_valor}
Siguiente clase: ""
estado: cruda
tags: []
Aclaración extra: 
---"""


# ─── Detección de videos pendientes ─────────────────────────────────────────

# Principal: YYYY-MM-DD_COD.(ext)   — sin número, el script lo calcula
VIDEO_PRINCIPAL = re.compile(
    r"^(\d{4}-\d{2}-\d{2})_([A-Z]{2,4})\.\w+$",
    re.IGNORECASE,
)

# Parte: YYYY-MM-DD_COD_pN.(ext)   — continuación de una grabación cortada
VIDEO_PARTE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})_([A-Z]{2,4})_p(\d+)\.\w+$",
    re.IGNORECASE,
)

# Nota de clase en vault: YYYY-MM-DD_NCOD.md  — para calcular número
NOTA_CLASE = re.compile(
    r"^(\d{4}-\d{2}-\d{2})_(\d+)([A-Z]{2,4})\.md$",
    re.IGNORECASE,
)


def detectar_videos_pendientes(
    videos_dir: Path,
    codigos_validos: set,
    extensiones: list,
) -> tuple[list[dict], list[dict]]:
    """
    Busca videos que matchean los patrones y no tienen .txt asociado.
    Devuelve dos listas: (principales, partes).
    """
    principales = []
    partes = []

    for ext in extensiones:
        for video in videos_dir.glob(f"*.{ext}"):
            # ¿Es un video principal?
            m = VIDEO_PRINCIPAL.match(video.name)
            if m:
                fecha, codigo = m.groups()
                codigo = codigo.upper()
                if codigo not in codigos_validos:
                    continue
                if video.with_suffix(".txt").exists():
                    continue
                principales.append(
                    {
                        "video": video,
                        "fecha": fecha,
                        "codigo": codigo,
                        "nombre_original": video.name,
                    }
                )
                continue

            # ¿Es una parte?
            m = VIDEO_PARTE.match(video.name)
            if m:
                fecha, codigo, num_parte = m.groups()
                codigo = codigo.upper()
                if codigo not in codigos_validos:
                    continue
                if video.with_suffix(".txt").exists():
                    continue
                partes.append(
                    {
                        "video": video,
                        "fecha": fecha,
                        "codigo": codigo,
                        "num_parte": int(num_parte),
                        "nombre_original": video.name,
                    }
                )
                continue

    principales.sort(key=lambda x: (x["fecha"], x["codigo"]))
    partes.sort(key=lambda x: (x["fecha"], x["codigo"], x["num_parte"]))
    return principales, partes


# ─── Cálculo automático del número de clase ──────────────────────────────────


def calcular_numero_clase(carpeta_materia: Path, codigo: str) -> int:
    """
    Busca notas de clase existentes en la carpeta de la materia que sigan
    el patrón YYYY-MM-DD_NCOD.md, toma la de número más alto y devuelve N+1.
    Si no hay ninguna, devuelve 1.
    """
    max_n = 0
    for archivo in carpeta_materia.glob("*.md"):
        m = NOTA_CLASE.match(archivo.name)
        if m:
            _, n_str, cod = m.groups()
            if cod.upper() == codigo.upper():
                max_n = max(max_n, int(n_str))
    return max_n + 1


def buscar_nota_principal_para_parte(
    carpeta_materia: Path,
    fecha: str,
    codigo: str,
) -> Path | None:
    """
    Busca la nota principal (YYYY-MM-DD_NCOD.md) del mismo día y código
    para appendear el texto de una parte. Devuelve la ruta o None.
    """
    for archivo in carpeta_materia.glob("*.md"):
        m = NOTA_CLASE.match(archivo.name)
        if m:
            f, _, cod = m.groups()
            if f == fecha and cod.upper() == codigo.upper():
                return archivo
    return None


# ─── Preview interactivo ─────────────────────────────────────────────────────


def mostrar_preview(
    principales: list[dict],
    partes: list[dict],
    numeros_calculados: dict[str, int],
    materias: dict,
) -> None:
    """
    Muestra al usuario qué va a hacer el script antes de ejecutar.
    numeros_calculados mapea "fecha_codigo" → N asignado.
    """
    total = len(principales) + len(partes)
    print(f"\nVideos pendientes encontrados: {total}\n")

    if principales:
        print("  PRINCIPALES:")
        for i, p in enumerate(principales, 1):
            n = numeros_calculados[f"{p['fecha']}_{p['codigo']}"]
            carpeta = materias[p["codigo"]]
            nombre_nuevo = f"{p['fecha']}_{n}{p['codigo']}"
            print(
                f"  {i}. {p['nombre_original']:40s} →  {carpeta}/{nombre_nuevo}.md  (clase #{n})"
            )
        print()

    if partes:
        print("  PARTES:")
        offset = len(principales)
        for i, p in enumerate(partes, offset + 1):
            carpeta = materias[p["codigo"]]
            # Buscar el N asignado al principal del mismo día/código
            clave = f"{p['fecha']}_{p['codigo']}"
            if clave in numeros_calculados:
                n = numeros_calculados[clave]
                nombre_principal = f"{p['fecha']}_{n}{p['codigo']}"
                print(
                    f"  {i}. {p['nombre_original']:40s} →  appendea a {carpeta}/{nombre_principal}.md"
                )
            else:
                # El principal ya existía en el vault (no es nuevo en esta corrida)
                print(
                    f"  {i}. {p['nombre_original']:40s} →  appendea a nota existente en {carpeta}/"
                )
        print()


def pedir_confirmacion() -> bool:
    """Pide confirmación al usuario. Devuelve True si confirma."""
    try:
        resp = input("  ¿Continuar? [s/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return resp in ("s", "si", "sí", "y", "yes")


# ─── Transcripción con WhisperX ──────────────────────────────────────────────


def transcribir(video_path: Path, whisperx_exe: Path, model: str) -> Path | None:
    """
    Ejecuta WhisperX directamente sobre el video.
    Devuelve la ruta al .txt generado (misma carpeta que el video).
    """
    print(f"\n  Transcribiendo: {video_path.name} ...")
    cmd = [
        str(whisperx_exe),
        str(video_path),
        "--model",
        model,
        "--output_format",
        "txt",
        "--output_dir",
        str(video_path.parent),
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


# ─── Manejo de notas en el vault ─────────────────────────────────────────────


def leer_txt(txt_path: Path) -> str:
    return txt_path.read_text(encoding="utf-8")


def clase_anterior(
    carpeta_materia: Path, fecha: str, num_clase: int, codigo: str
) -> str | None:
    """
    Busca la nota de clase anterior en la carpeta de la materia.
    Ordena por nombre (que empieza con fecha) y devuelve el nombre sin extensión
    de la nota inmediatamente anterior a la actual.
    """
    patron = re.compile(
        rf"^\d{{4}}-\d{{2}}-\d{{2}}_\d+{re.escape(codigo)}\.md$", re.IGNORECASE
    )
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
    Cubre dos casos: campo vacío ("") y campo con link previo ([[...]]).
    """
    if not nota_anterior_path.exists():
        return
    contenido = nota_anterior_path.read_text(encoding="utf-8")

    nuevo = re.sub(
        r'(Siguiente clase:\s*)"?\[\[.*?\]\]"?',
        f'\\1"[[{nombre_nueva}]]"',
        contenido,
    )
    # Cubre el caso donde Siguiente clase estaba vacío ("")
    nuevo = re.sub(
        r'(Siguiente clase:\s*)""',
        f'\\1"[[{nombre_nueva}]]"',
        nuevo,
    )

    if nuevo != contenido:
        nota_anterior_path.write_text(nuevo, encoding="utf-8")
        print(f"  Actualizado 'Siguiente clase' en: {nota_anterior_path.name}")


def crear_nota_transcripcion(
    carpeta_transcripciones: Path, nombre_base: str, texto: str
):
    """
    Crea [Materia]/Transcripciones/YYYY-MM-DD_NCOD_t.md con solo el texto crudo.
    """
    ruta = carpeta_transcripciones / f"{nombre_base}_t.md"
    ruta.write_text(texto, encoding="utf-8")
    print(f"  Transcripción cruda: {ruta.relative_to(ruta.parent.parent.parent)}")


def crear_nota_clase(
    carpeta_materia: Path, nombre_base: str, frontmatter: str, texto: str
):
    """
    Crea [Materia]/YYYY-MM-DD_NCOD.md con el frontmatter procesado + texto crudo.
    """
    ruta = carpeta_materia / f"{nombre_base}.md"
    ruta.write_text(frontmatter + "\n\n" + texto, encoding="utf-8")
    print(f"  Nota de clase creada: {ruta.relative_to(carpeta_materia.parent)}")
    return ruta


def appendear_a_nota(nota_path: Path, texto: str, num_parte: int):
    """
    Appendea el texto de una parte al final de la nota principal existente,
    con un separador visual.
    """
    separador = f"\n\n---\n*[Parte {num_parte}]*\n\n"
    contenido = nota_path.read_text(encoding="utf-8")
    nota_path.write_text(contenido + separador + texto, encoding="utf-8")
    print(f"  Texto de parte {num_parte} appendeado a: {nota_path.name}")


def appendear_a_transcripcion(
    carpeta_transcripciones: Path, nombre_base: str, texto: str, num_parte: int
):
    """
    Appendea el texto de una parte al archivo _t.md existente.
    """
    ruta = carpeta_transcripciones / f"{nombre_base}_t.md"
    if ruta.exists():
        separador = f"\n\n---\n*[Parte {num_parte}]*\n\n"
        contenido = ruta.read_text(encoding="utf-8")
        ruta.write_text(contenido + separador + texto, encoding="utf-8")
        print(f"  Texto de parte {num_parte} appendeado a: {ruta.name}")
    else:
        print(f"  [AVISO] No se encontró {ruta.name} para appendear parte {num_parte}")


# ─── Renombrado de videos ───────────────────────────────────────────────────


def renombrar_video(video_path: Path, nombre_nuevo: str) -> Path:
    """
    Renombra el video en la carpeta de videos, conservando la extensión.
    Devuelve la nueva ruta.
    """
    nueva_ruta = video_path.parent / f"{nombre_nuevo}{video_path.suffix}"
    video_path.rename(nueva_ruta)
    print(f"  Renombrado: {video_path.name} → {nueva_ruta.name}")
    return nueva_ruta


# ─── Flujo principal ─────────────────────────────────────────────────────────


def procesar(config: dict, auto_yes: bool = False):
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

    principales, partes = detectar_videos_pendientes(
        videos_dir, codigos_validos, extensiones
    )

    if not principales and not partes:
        print("No hay videos pendientes de transcribir.")
        return

    # ── Calcular números de clase para cada principal ──
    # Se calculan todos ANTES de procesar para que el preview sea correcto.
    # Si hay dos principales del mismo código, se asignan N y N+1 en orden.
    numeros_calculados = {}  # "fecha_codigo" → N
    # Contadores temporales para manejar múltiples videos del mismo código
    offset_por_codigo = {}  # codigo → cuántos ya se asignaron

    for p in principales:
        codigo = p["codigo"]
        carpeta_materia = vault_dir / materias[codigo]

        if codigo not in offset_por_codigo:
            offset_por_codigo[codigo] = 0

        n = calcular_numero_clase(carpeta_materia, codigo) + offset_por_codigo[codigo]
        numeros_calculados[f"{p['fecha']}_{p['codigo']}"] = n
        offset_por_codigo[codigo] += 1

    # ── Preview ──
    mostrar_preview(principales, partes, numeros_calculados, materias)

    if not auto_yes:
        if not pedir_confirmacion():
            print("Abortado por el usuario.")
            return

    # ── Pasada 1: procesar principales ──
    for p in principales:
        video = p["video"]
        fecha = p["fecha"]
        codigo = p["codigo"]
        n = numeros_calculados[f"{fecha}_{codigo}"]
        nombre_base = f"{fecha}_{n}{codigo}"
        carpeta_materia = vault_dir / materias[codigo]
        carpeta_transcripciones = carpeta_materia / "Transcripciones"

        print(f"\n[{codigo}] Procesando: {video.name} → clase #{n}")

        # 1. Renombrar video
        video = renombrar_video(video, nombre_base)

        # 2. Transcribir
        txt_path = transcribir(video, whisperx_exe, model)
        if txt_path is None:
            print(f"  [SKIP] Se omite {video.name} por error en transcripción.")
            continue

        # 3. Leer texto
        texto = leer_txt(txt_path)

        # 4. Crear carpeta Transcripciones si no existe
        carpeta_transcripciones.mkdir(parents=True, exist_ok=True)

        # 5. Crear nota _t (texto crudo)
        crear_nota_transcripcion(carpeta_transcripciones, nombre_base, texto)

        # 6. Buscar clase anterior (no aplica para OTR, son videos sueltos)
        anterior = None
        if codigo != "OTR":
            anterior = clase_anterior(carpeta_materia, fecha, n, codigo)
            if anterior:
                print(f"  Clase anterior detectada: {anterior}")
            else:
                print(f"  No se encontró clase anterior (es la primera de {codigo})")

        # 7. Leer frontmatter del template
        fm_raw = leer_template_frontmatter(vault_dir, codigo)
        if fm_raw:
            frontmatter = aplicar_valores_al_frontmatter(fm_raw, anterior, fecha)
        else:
            print(f"  Usando frontmatter genérico para {codigo}")
            frontmatter = frontmatter_generico(anterior)

        # 8. Crear nota de clase
        crear_nota_clase(
            carpeta_materia=carpeta_materia,
            nombre_base=nombre_base,
            frontmatter=frontmatter,
            texto=texto,
        )

        # 9. Actualizar "Siguiente clase" en la nota anterior (no aplica para OTR)
        if anterior and codigo != "OTR":
            nota_anterior_path = carpeta_materia / f"{anterior}.md"
            actualizar_siguiente_clase(nota_anterior_path, nombre_base)

    # ── Pasada 2: procesar partes ──
    for p in partes:
        video = p["video"]
        fecha = p["fecha"]
        codigo = p["codigo"]
        num_parte = p["num_parte"]
        carpeta_materia = vault_dir / materias[codigo]
        carpeta_transcripciones = carpeta_materia / "Transcripciones"

        print(f"\n[{codigo}] Procesando parte {num_parte}: {video.name}")

        # Buscar la nota principal a la que appendear
        nota_principal = buscar_nota_principal_para_parte(
            carpeta_materia, fecha, codigo
        )

        if nota_principal is None:
            # Quizá el principal se acaba de crear en esta corrida,
            # buscar con la clave de numeros_calculados
            clave = f"{fecha}_{codigo}"
            if clave in numeros_calculados:
                n = numeros_calculados[clave]
                nombre_principal = f"{fecha}_{n}{codigo}"
                nota_principal = carpeta_materia / f"{nombre_principal}.md"

        if nota_principal is None or not nota_principal.exists():
            print(
                f"  [SKIP] No se encontró nota principal para {video.name}. "
                f"Procesá primero el video principal del {fecha}."
            )
            continue

        nombre_base_principal = nota_principal.stem  # ej: 2026-03-10_2MYS

        # 1. Renombrar video de parte: COD_pN → NCOD_pN
        nombre_parte_nuevo = f"{nombre_base_principal}_p{num_parte}"
        video = renombrar_video(video, nombre_parte_nuevo)

        # 2. Transcribir
        txt_path = transcribir(video, whisperx_exe, model)
        if txt_path is None:
            print(f"  [SKIP] Se omite {video.name} por error en transcripción.")
            continue

        # 3. Leer texto
        texto = leer_txt(txt_path)

        # 4. Appendear a la nota principal
        appendear_a_nota(nota_principal, texto, num_parte)

        # 5. Appendear a la transcripción cruda
        appendear_a_transcripcion(
            carpeta_transcripciones, nombre_base_principal, texto, num_parte
        )

    print("\n")
    print("Procesamiento completado.")


# ─── Comienzo ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Procesa videos de clases: transcribe con WhisperX y genera notas en Obsidian.",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Ejecutar sin pedir confirmación (skip preview interactivo)",
    )
    args = parser.parse_args()

    config = cargar_config()
    procesar(config, auto_yes=args.yes)
