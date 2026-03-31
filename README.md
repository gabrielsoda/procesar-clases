# procesar-clases

Pipeline para automatizar el procesamiento de clases grabadas: transcripción, recorte de silencios, subida a YouTube y limpieza de archivos.

Nació como herramienta personal para la carrera TUIA (Tec. Universitaria en Inteligencia Artificial) pero funciona para cualquier contexto donde grabes clases y quieras procesarlas de forma sistemática. Lo único manual que se debe hacer es cambiar el nombre del video (como sale de OBS) o archivo a transcribir y procesar.

## Qué hace

Tenés una grabación de clase y querés:

1. **Transcribirla** con WhisperX y generar una nota de esa transcripción en tu vault de Obsidian
2. **Recortarle los silencios** para que el video quede limpio
3. **Subirla a YouTube** (privada, organizada por playlists)
4. **Limpiar** los archivos locales una vez que todo está subido

Cada paso es un script independiente que detecta automáticamente qué tiene pendiente. Podés ejecutarlos por separado o encadenados con un solo comando.

## Pipeline completo

```
pc  → procesar_clases.py    Transcribe con WhisperX, genera notas en Obsidian
qs  → quitar_silencios.py   Recorta silencios con auto-editor
sc  → subir_clases.py       Sube a YouTube como video privado
lc  → limpiar_clases.py     Elimina archivos ya subidos (procesados + originales)
```

Cada script tiene preview interactivo: te muestra qué va a hacer y te pide confirmación antes de ejecutar. El flag `-y` skipea la confirmación (excepto `lc`, que siempre pregunta porque borra archivos).

## Requisitos

- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/)** — gestor de proyecto y runner de scripts
- **[WhisperX](https://github.com/m-bain/whisperX)** — transcripción de audio (necesita CUDA para GPU)
- **[auto-editor](https://auto-editor.com/)** — recorte de silencios
- **[ffmpeg](https://ffmpeg.org/)** — manipulación de video (lo usa auto-editor y el script de silencios)
- **Cuenta de Google** con acceso a YouTube Data API v3 (solo si querés subir a YouTube)

### Sobre WhisperX

WhisperX necesita su propio entorno virtual con PyTorch + CUDA. No se instala como dependencia de este proyecto, sino como ejecutable aparte. Seguí las instrucciones del [repo de WhisperX](https://github.com/m-bain/whisperX) para instalarlo. En `config.json` apuntás a su ejecutable.

### Sobre auto-editor

El ejecutable de auto-editor va en la carpeta `bin/` del proyecto. Descargalo desde [auto-editor.com](https://auto-editor.com/) y ubicalo en `bin/auto-editor.exe` (Windows) o `bin/auto-editor` (Linux). La ruta se configura en `config.json`.

## Instalación

```bash
git clone https://github.com/gabrielsoda/procesar-clases.git
cd procesar-clases
uv sync
```

Esto instala las dependencias de Python (google-api-python-client, etc.). **WhisperX y auto-editor se instalan aparte**.

## Configuración

Copiá `config.example.json` a `config.json` y completá con tus rutas:

```bash
cp config.example.json config.json
```

```jsonc
{
  // Carpeta donde están tus grabaciones (donde OBS guarda los videos)
  "videos_dir": "C:\\Users\\TU_USUARIO\\Videos",

  // Ruta al vault de Obsidian donde se generan las notas
  "vault_dir": "C:\\Users\\TU_USUARIO\\path\\al\\vault",

  // Ejecutable de WhisperX
  "whisperx_exe": "C:\\Users\\TU_USUARIO\\whisperx-env\\Scripts\\whisperx.exe",

  // Modelo de Whisper a usar
  "whisperx_model": "large-v3",

  // Extensiones de archivo que el script busca
  "file_extensions": ["mkv", "mp4", "m4a", "mp3", "ogg", "wav", "webm"],

  // Mapeo de códigos a nombres de materia (y carpetas en el vault)
  "materias": {
    "AA2": "Aprendizaje Automático 2",
    "MYS": "Modelado y simulación",
    "COD": "Nombre de la materia"
  },

  // Carpeta de salida para videos procesados (sin silencios)
  "processed_videos_path": "C:\\Users\\TU_USUARIO\\Videos\\Post_auto-editor",

  // Ruta al ejecutable de auto-editor (relativa al proyecto)
  "auto_editor_exe": "bin/auto-editor.exe",

  // Ruta al client_secret.json de Google (relativa al proyecto)
  "youtube_credentials": "credentials/client_secret.json",

  // Mapeo de códigos a IDs de playlists de YouTube
  "youtube_playlists": {
    "AA2": "",
    "MYS": "PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "COD": ""
  }
}
```

### Rutas en Linux

Las rutas en `config.json` usan el formato de tu sistema operativo. En Linux sería:

```json
{
  "videos_dir": "/home/tu_usuario/Videos",
  "vault_dir": "/home/tu_usuario/Obsidian/Mi Vault",
  "whisperx_exe": "/home/tu_usuario/whisperx-env/bin/whisperx",
  "processed_videos_path": "/home/tu_usuario/Videos/Post_auto-editor",
  "auto_editor_exe": "bin/auto-editor"
}
```

### Materias y códigos

Cada materia se identifica con un código de 2 a 4 letras (ej: `AA2`, `MYS`, `GDP`). Este código aparece en el nombre del video y se usa para:

- Determinar en qué carpeta del vault va la nota
- Asignar la playlist de YouTube correspondiente
- Calcular el número de clase automáticamente

Agregá tantas materias como necesites en el campo `materias`. Si una materia no tiene playlist de YouTube, dejá el valor vacío (`""`).

## Convención de nombres de video

El sistema se basa en cómo nombrás tus archivos. Después de grabar con OBS (o lo que uses), renombrá el archivo siguiendo este formato:

```
OBS -> YYYY-MM-DD_HH-mm-ss.ext
cambialo a -> YYYY-MM-DD_CÓDIGO.ext

Ejemplos:
  2026-03-10_AA2.mkv        ← clase de Aprendizaje Automático 2 del 10/03
  2026-03-12_MYS.mp4        ← clase de Modelado y Simulación del 12/03
  2026-03-11_BDD.m4a        ← audio de clase de Bases de Datos del 11/03
```

**No pongas el número de clase.** El script lo calcula automáticamente leyendo las notas existentes en el vault. Si ya hay 2 clases de AA2, la próxima va a ser la #3.

### Grabaciones cortadas (partes)

Si la grabación se cortó y quedaron dos (o más) archivos de la misma clase, nombrá las partes adicionales con `_p2`, `_p3`, etc.:

```
2026-03-10_AA2.mkv         ← primera parte
2026-03-10_AA2_p2.mkv      ← segunda parte
2026-03-10_AA2_p3.mkv      ← tercera parte (si hubo otro corte)
```

Los scripts las detectan, procesan por separado, y las combinan automáticamente en un solo archivo final.

## Uso

A continuación se muestran ejecuciones individuales de cada script, pero como es posible que lo ejecutes con bastante frecuencia, se recomienda agregar aliases a la terminal.
### Opción 1: Script por script

```bash
# Transcribir y generar notas en Obsidian
uv run procesar_clases.py

# Recortar silencios
uv run quitar_silencios.py

# Subir a YouTube
uv run subir_clases.py

# Limpiar archivos ya subidos
uv run limpiar_clases.py
```

Todos muestran un preview interactivo antes de ejecutar. Agregá `-y` para skipear la confirmación:

```bash
uv run procesar_clases.py -y
uv run quitar_silencios.py -y
uv run subir_clases.py -y
# limpiar_clases.py no acepta -y (siempre pide confirmación)
```

### Opción 2: Pipeline completo

Si configurás los aliases (ver abajo), con un solo comando se ejecuta todo:

```
clases          # ejecuta pc → qs → sc → lc, pidiendo confirmación en cada paso
clases -y       # skipea confirmación en pc, qs y sc (lc siempre pregunta)
```

Si algún paso falla, el pipeline se detiene. Si un paso no tiene trabajo pendiente, imprime un mensaje y pasa al siguiente.

### Flag de idioma (solo `procesar_clases.py`)

WhisperX autodetecta el idioma, pero si querés forzarlo:

```bash
uv run procesar_clases.py -l es     # forzar español
uv run procesar_clases.py -l en     # forzar inglés
```

## Detalle de cada script

### `procesar_clases.py` (alias: `pc`)

Detecta videos en `videos_dir` que matcheen el patrón de nombre y no tengan `.txt` asociado (indicador de que ya fue transcripto).

Flujo:
1. Calcula el número de clase leyendo las notas existentes en el vault
2. Renombra el video: `2026-03-10_AA2.mkv` → `2026-03-10_3AA2.mkv` (clase #3)
3. Transcribe con WhisperX (una sola llamada, carga el modelo una vez)
4. Genera la nota de clase con frontmatter desde templates de Obsidian
5. Genera la transcripción cruda en la subcarpeta `Transcripciones/`
6. Actualiza los links de navegación (Clase anterior / Siguiente clase)

Para partes (`_p2`, `_p3`...), appendea el texto a la nota principal existente.

### `quitar_silencios.py` (alias: `qs`)

Detecta videos ya renombrados (con número de clase) en `videos_dir` que no tengan archivo correspondiente en `processed_videos_path`.

El menú interactivo muestra cada archivo con una acción por defecto según su tipo:

| Tipo | Acción por defecto | Opciones disponibles |
|---|---|---|
| Video | Recortar silencios | recortar / copiar sin recortar / saltear |
| Audio | Copiar sin recortar | convertir a video + recortar / copiar / saltear |

Para grabaciones multipart, procesa cada parte y las concatena en un solo archivo final. Detecta automáticamente si los codecs coinciden para evitar re-encode innecesario.

### `subir_clases.py` (alias: `sc`)

Detecta videos en `processed_videos_path` que no tengan el marker `.uploaded`. Los sube a YouTube como videos privados, los agrega a la playlist configurada, y crea el marker.

### `limpiar_clases.py` (alias: `lc`)

Detecta videos en `processed_videos_path` que tengan el marker `.uploaded` (ya subidos a YouTube). Elimina:
- El video procesado
- El marker `.uploaded`
- El video original en `videos_dir` (si existe)

Siempre pide confirmación, incluso con `clases -y`. Permite saltear la eliminación de archivos individuales.

## Aliases recomendados

### PowerShell (Windows)

Agregá esto a tu `$PROFILE` (generalmente `Microsoft.PowerShell_profile.ps1`):

```powershell
# Procesar clases: transcribir videos y generar notas en Obsidian
function ProcesarClases {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )
    uv run "C:\ruta\a\procesar-clases\procesar_clases.py" @Args
}
Set-Alias -Name pc -Value ProcesarClases

# Quitar silencios con auto-editor
function QuitarSilencios {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )
    uv run "C:\ruta\a\procesar-clases\quitar_silencios.py" @Args
}
Set-Alias -Name qs -Value QuitarSilencios

# Subir a YouTube
function SubirClases {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )
    uv run "C:\ruta\a\procesar-clases\subir_clases.py" @Args
}
Set-Alias -Name sc -Value SubirClases

# Limpiar archivos ya subidos
function LimpiarClases {
    param(
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Args
    )
    uv run "C:\ruta\a\procesar-clases\limpiar_clases.py" @Args
}
Set-Alias -Name lc -Value LimpiarClases

# Pipeline completo: pc → qs → sc → lc
function ProcesarClasesCompleto {
    param([switch]$y)
    $flags = @()
    if ($y) { $flags += "-y" }

    uv run "C:\ruta\a\procesar-clases\procesar_clases.py" @flags
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error en procesar_clases.py (código $LASTEXITCODE). Abortando pipeline." -ForegroundColor Red
        return
    }
    uv run "C:\ruta\a\procesar-clases\quitar_silencios.py" @flags
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error en quitar_silencios.py (código $LASTEXITCODE). Abortando pipeline." -ForegroundColor Red
        return
    }
    uv run "C:\ruta\a\procesar-clases\subir_clases.py" @flags
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error en subir_clases.py (código $LASTEXITCODE). Abortando pipeline." -ForegroundColor Red
        return
    }
    uv run "C:\ruta\a\procesar-clases\limpiar_clases.py"
}
Set-Alias -Name clases -Value ProcesarClasesCompleto
```

Reemplazá `C:\ruta\a\procesar-clases\` con la ruta real donde clonaste el proyecto.

### Bash / Zsh (Linux / macOS)

Agregá esto a tu `.bashrc` o `.zshrc`:

```bash
PROCESAR_CLASES_DIR="$HOME/proyectos/procesar-clases"

alias pc="uv run $PROCESAR_CLASES_DIR/procesar_clases.py"
alias qs="uv run $PROCESAR_CLASES_DIR/quitar_silencios.py"
alias sc="uv run $PROCESAR_CLASES_DIR/subir_clases.py"
alias lc="uv run $PROCESAR_CLASES_DIR/limpiar_clases.py"

clases() {
    local flags=()
    [[ "$1" == "-y" ]] && flags+=("-y")

    uv run "$PROCESAR_CLASES_DIR/procesar_clases.py" "${flags[@]}" || { echo "Error en procesar_clases.py. Abortando."; return 1; }
    uv run "$PROCESAR_CLASES_DIR/quitar_silencios.py" "${flags[@]}" || { echo "Error en quitar_silencios.py. Abortando."; return 1; }
    uv run "$PROCESAR_CLASES_DIR/subir_clases.py" "${flags[@]}" || { echo "Error en subir_clases.py. Abortando."; return 1; }
    uv run "$PROCESAR_CLASES_DIR/limpiar_clases.py"
}
```

Ajustá `PROCESAR_CLASES_DIR` a donde esté el proyecto.

## Subida a YouTube: setup de autenticación

Para usar `subir_clases.py` necesitás configurar OAuth con la YouTube Data API v3. Si no vas a subir videos a YouTube, podés saltear esta sección y usar solo `pc` y `qs`.

### 1. Crear proyecto en Google Cloud Console

1. Andá a [Google Cloud Console](https://console.cloud.google.com/)
2. Creá un proyecto nuevo (o usá uno existente)
3. Habilitá la **YouTube Data API v3** en APIs & Services → Library
4. En APIs & Services → Credentials → Create Credentials → **OAuth client ID**
5. Tipo de aplicación: **Desktop app**
6. Descargá el JSON y guardalo como `credentials/client_secret.json` en el proyecto

### 2. Primera ejecución

La primera vez que ejecutes `sc` (o `uv run subir_clases.py`), se abre el navegador para que autorices el acceso a tu cuenta de YouTube. Después de autorizar, se guarda un token en `credentials/youtube_token.json` que se renueva automáticamente.

### 3. Playlists

En `config.json`, mapeá cada código de materia a su playlist ID de YouTube:

```json
"youtube_playlists": {
    "AA2": "PLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
    "MYS": "PLyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"
}
```

Para obtener el ID de una playlist, abrila en YouTube y copiá el valor de `list=` de la URL. Si una materia no tiene playlist, dejá el valor vacío y el video se sube sin asignar a ninguna.

## Estructura de archivos generada en el vault de Obsidian

```
[Materia]/
├── Transcripciones/
│   └── YYYY-MM-DD_NCOD_t.md       ← texto crudo de WhisperX
├── YYYY-MM-DD_NCOD.md              ← nota con frontmatter (estado: cruda)
├── Kanban [COD].md                 ← tablero de tareas (opcional, lo creás vos)
└── Clases [COD].base               ← vista de clases por estado (Obsidian Bases)
```

Las notas de clase incluyen frontmatter con campos como `estado` (cruda / procesando / procesada), links de navegación (Clase anterior / Siguiente clase), y el texto de la transcripción. El frontmatter se toma de templates de Obsidian ubicados en `Templates/Clase de {CODIGO}.md` dentro del vault.

## Estructura del proyecto

```
procesar-clases/
├── procesar_clases.py       ← transcripción + notas en Obsidian
├── quitar_silencios.py      ← recorte de silencios con auto-editor
├── subir_clases.py          ← subida a YouTube
├── limpiar_clases.py        ← limpieza de archivos ya subidos
├── config.example.json      ← template de configuración
├── config.json              ← tu configuración (ignorado por git)
├── pyproject.toml           ← dependencias del proyecto
├── bin/                     ← ejecutable de auto-editor (ignorado por git)
└── credentials/             ← OAuth de YouTube (ignorado por git)
```

## Licencia

Podés hacer lo que quieras con esto.
