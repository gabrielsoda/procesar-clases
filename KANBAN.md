# Kanban — procesar-clases

<!-- Columnas: Backlog | In Progress | Done -->
<!-- Mover ítems entre columnas a medida que avanzás -->

---

## Backlog

### `limpiar_clases.py`
- **Borrar partes al limpiar** — cuando se limpia un video multipart (ej: `2026-03-31_4GDP.mp4`), también borrar los archivos `_p2`, `_p3`, etc. del `videos_dir`. Actualmente solo borra el original principal, dejando las partes huérfanas que `qs` vuelve a detectar como pendientes.

### `subir_clases.py`
- **Manejar token expirado** — cuando `creds.refresh()` falla con `RefreshError`, borrar `youtube_token.json` automáticamente y re-autenticar en vez de crashear con traceback.


### Videos "otros" (todos los scripts)
- **Fuzzy matching de códigos mal tipeados** — cuando un video cae en "otros" porque su código no matchea ninguno del config, chequear similitud con códigos conocidos (ej: `AA3` vs `AA2`) y avisar al usuario antes de procesarlo como "otro". No implementar aún, solo anotado para más adelante.

### README.md
- **Documentar setup de YouTube** — agregar sección explicando cómo configurar la autenticación OAuth (crear proyecto en Google Cloud Console, descargar `client_secret.json`, primera ejecución que abre el navegador) y cómo funcionan las playlists en `config.json`.

### UI
- **Rich** — agregar colores a los menúes interactivos para simplificar la visualización de la información.

---

## In Progress

_(nada en curso)_

---

## Done

### `quitar_silencios.py`
- **Eliminar chequeo de `.txt`** en `detectar_pendientes()` — el criterio de "pendiente" es solo matchear el patrón y no tener archivo en `processed_videos_path`.
- **Unir partes automáticamente** — cuando se detectan `_p2`, `_p3`, etc., recortarles silencios por separado y concatenarlos en un único archivo final.
- **Mostrar barra de progreso de auto-editor** — cambiar `capture_output=True` para que auto-editor imprima directo a la terminal.

### `pyproject.toml`
- **Actualizar campo deprecado** — cambiar `[tool.uv] dev-dependencies = []` por `[dependency-groups] dev = []`.

### PowerShell
- **Alias `qs`** para `quitar_silencios.py`.
- **Alias `clases`** — pipeline completo `pc → qs → sc → lc` en secuencia.
- **Propagar flag `-l` al pipeline `clases`** — `-l` se agrega a `ProcesarClasesCompleto` y se propaga solo a `pc` para forzar el idioma de transcripción en WhisperX.

### `subir_clases.py`
- **Subida a YouTube** — nuevo script que toma los videos de `processed_videos_path` y los sube via YouTube Data API v3.
- **Idioma del video (`es-419`)** — agregado `defaultLanguage: "es-419"` al snippet de la subida para que YouTube lo detecte como Español (Latinoamérica) automáticamente.

### `subir_clases.py`
- **Idioma configurable** — flag `-l`/`--lang` con mapeo WhisperX → BCP-47, prompt interactivo (español/inglés/otro) si no se pasa flag, propagado en el pipeline `clases` vía PowerShell.

### Videos "otros" (todos los scripts)
- **Eliminar código `OTR`** — los 4 scripts (`procesar_clases`, `quitar_silencios`, `subir_clases`, `limpiar_clases`) ahora detectan y procesan videos "otros" por nombre original, sin necesidad del código comodín `OTR`.
