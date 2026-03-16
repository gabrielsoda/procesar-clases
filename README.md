# tuia-procesar-clases

Script personal para automatizar el ingreso de clases grabadas al vault de Obsidian (TUIA). Flujo diseñado luego de bastante experiencia 

## Flujo de trabajo

```
OBS graba → YYYY-MM-DD HH-MM-SS.mkv
    ↓ (renombrado manual, SIN número)
YYYY-MM-DD_COD.mkv              (ej: 2026-03-10_AA2.mkv)
    ↓ (script: pc)
Preview: muestra qué va a hacer + pide confirmación
    ↓
Calcula número de clase leyendo notas existentes en el vault
    ↓
Renombra video: 2026-03-10_AA2.mkv → 2026-03-10_3AA2.mkv (clase #3)
    ↓
WhisperX → .txt en C:\Users\Gabi\Videos
    ↓
[Materia]/Transcripciones/YYYY-MM-DD_NCOD_t.md   (texto crudo, sin frontmatter)
[Materia]/YYYY-MM-DD_NCOD.md                      (frontmatter + texto, estado: cruda)
```

Los links `Clase anterior` / `Siguiente clase` se actualizan automáticamente entre notas.

### Grabaciones cortadas (partes)

Si OBS se corta y quedan dos archivos de la misma clase:

```
2026-03-10_AA2.mkv       → primera parte (se procesa normal)
2026-03-10_AA2_p2.mkv    → segunda parte (se transcribe y appendea a la nota principal)
```

## Uso

```powershell
pc          # muestra preview y pide confirmación
pc -y       # ejecuta sin pedir confirmación
```

El alias `pc` (configurado en el perfil de PowerShell) ejecuta `uv run procesar_clases.py` desde cualquier directorio.
El script detecta todos los videos en `C:\Users\Gabi\Videos` que no tienen `.txt` asociado y los procesa en batch.

### Preview interactivo

Antes de ejecutar, el script muestra exactamente qué va a hacer:

```
Videos pendientes encontrados: 3

  PRINCIPALES:
  1. 2026-03-10_AA2.mkv       →  🧠 Aprendizaje Automático 2/2026-03-10_3AA2.md  (clase #3)
  2. 2026-03-10_OTR.mp4       →  Otros/2026-03-10_1OTR.md  (clase #1)

  PARTES:
  3. 2026-03-10_AA2_p2.mkv    →  appendea a 🧠 Aprendizaje Automático 2/2026-03-10_3AA2.md

  ¿Continuar? [s/N]:
```

## Configuración (`config.json`)

| Campo | Descripción |
|---|---|
| `videos_dir` | Carpeta donde OBS guarda las grabaciones |
| `vault_dir` | Ruta al vault de Obsidian |
| `whisperx_exe` | Ejecutable de WhisperX dentro del venv |
| `whisperx_model` | Modelo a usar (por defecto: `large-v3`) |
| `file_extensions` | Extensiones soportadas ("mkv", "mp4", "m4a", "mp3", "ogg", "wav", "webm") |
| `materias` | Mapeo código → nombre de carpeta en el vault |

Para agregar o cambiar materias, editá el campo `materias` en `config.json`.

## Convención de nombres de video

```
YYYY-MM-DD_CÓDIGO.(mkv|mp4|m4a)

El usuario renombra SIN número. El script calcula el número
automáticamente leyendo las notas existentes en el vault.

Ejemplos de renombrado manual:
  2026-03-10_AA2.mkv       → script renombra a 2026-03-10_3AA2.mkv (clase #3)
  2026-03-12_MYS.mkv       → script renombra a 2026-03-12_2MYS.mkv (clase #2)
  2026-03-11_GDP.mp4       → script renombra a 2026-03-11_10GDP.mp4 (clase #10)
  2026-03-03_OTR.mkv       → script renombra a 2026-03-03_1OTR.mkv (clase #1)

Para grabaciones cortadas:
  2026-03-10_AA2_p2.mkv    → script renombra a 2026-03-10_3AA2_p2.mkv
```

## Estados de una clase (campo `estado` en frontmatter)

| Valor | Significado |
|---|---|
| `cruda` | Transcripción como sale de Whisper, sin procesar |
| `procesando` | En proceso de limpieza y resumen |
| `procesada` | Resumen final completo |

El campo `estado` es la fuente de verdad para el tracking. Se visualiza en Obsidian Bases (`Clases [COD].base` dentro de cada carpeta de materia).

## Dependencias

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) como gestor de proyecto
- WhisperX instalado en `C:\Users\Gabi\whisperx-env`

## Estructura del vault generada

```
[Materia]/
├── Transcripciones/
│   └── YYYY-MM-DD_NCOD_t.md       ← texto crudo de Whisper
├── YYYY-MM-DD_NCOD.md              ← nota con frontmatter (estado: cruda)
├── Kanban [COD].md                 ← tablero de tareas sueltas de la materia
└── Clases [COD].base               ← vista de clases agrupadas por estado
```
