# tuia-procesar-clases

Script personal para automatizar el ingreso de clases grabadas al vault de Obsidian (TUIA). Flujo diseñado luego de bastante experiencia 

## Flujo de trabajo

```
OBS graba → YYYY-MM-DD HH-MM-SS.mkv
    ↓ (renombrado manual)
YYYY-MM-DD_[N][COD].mkv         (ej: 2026-03-10_3AA2.mkv)
    ↓ (script: pc)
WhisperX → .txt en C:\Users\Gabi\Videos
    ↓
[Materia]/Transcripciones/YYYY-MM-DD_[N][COD]_t.md   (texto crudo, sin frontmatter)
[Materia]/YYYY-MM-DD_[N][COD].md                      (frontmatter + texto, estado: cruda)
```

Los links `Clase anterior` / `Siguiente clase` se actualizan automáticamente entre notas.

## Uso

```powershell
pc
```

El alias `pc` (configurado en el perfil de powershell) ejecuta `uv run procesar_clases.py` desde cualquier directorio.
El script detecta todos los videos en `C:\Users\Gabi\Videos` que no tienen `.txt` asociado y los procesa en batch.

## Configuración (`config.json`)

| Campo | Descripción |
|---|---|
| `videos_dir` | Carpeta donde OBS guarda las grabaciones |
| `vault_dir` | Ruta al vault de Obsidian |
| `whisperx_exe` | Ejecutable de WhisperX dentro del venv |
| `whisperx_model` | Modelo a usar (por defecto: `large-v3`) |
| `video_extensions` | Extensiones soportadas (`mkv`, `mp4`) |
| `materias` | Mapeo código → nombre de carpeta en el vault |

Para agregar o cambiar materias, editá el campo `materias` en `config.json`.

## Convención de nombres de video

```
YYYY-MM-DD_[N][COD].(mkv|mp4)

Ejemplos:
  2026-03-10_3AA2.mkv    → clase 3 de Aprendizaje Automático 2
  2026-03-12_2MYS.mkv    → clase 2 de Modelado y Simulación
  2026-03-11_10GP.mkv    → clase 10 de Gestión de Proyectos
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
│   └── YYYY-MM-DD_[N][COD]_t.md   ← texto crudo de Whisper
├── YYYY-MM-DD_[N][COD].md          ← nota con frontmatter (estado: cruda)
├── Kanban [COD].md                 ← tablero de tareas sueltas de la materia
└── Clases [COD].base               ← vista de clases agrupadas por estado
```
