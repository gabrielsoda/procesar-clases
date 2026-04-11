# Kanban — procesar-clases

<!-- Columnas: Backlog | In Progress | Done -->
<!-- Mover ítems entre columnas a medida que avanzás -->

---

## Backlog

### `limpiar_clases.py`
- **Borrar partes al limpiar** — cuando se limpia un video multipart (ej: `2026-03-31_4GDP.mp4`), también borrar los archivos `_p2`, `_p3`, etc. del `videos_dir`. Actualmente solo borra el original principal, dejando las partes huérfanas que `qs` vuelve a detectar como pendientes.

### `subir_clases.py`
- **Manejar token expirado** — cuando `creds.refresh()` falla con `RefreshError`, borrar `youtube_token.json` automáticamente y re-autenticar en vez de crashear con traceback.
- **Idioma configurable por video** — el flag `-l` que se pasa a WhisperX para la transcripción debe propagarse también a `subir_clases.py` para setear `defaultLanguage` en YouTube. Como WhisperX usa códigos cortos (`es`, `en`, `it`) y YouTube usa BCP-47, hace falta un mapeo interno: español → `es-419`, inglés → `en`, y los idiomas comunes (italiano, portugués, francés, alemán, ruso, chino, japonés, etc.) → su BCP-47 correspondiente. Si no se pasa `-l`, se usa `es-419` como default. Implica propagar el flag por todo el pipeline (`pc → sc`) y desde `ProcesarClasesCompleto` en PowerShell.


### Videos misceláneos (todos los scripts)
- **Eliminar código `OTR`** — es un comodín artificial que obliga a renombrar manualmente videos misceláneos con la convención `YYYY-MM-DD_OTR.mkv`. Si el nombre del archivo no matchea ningún código conocido, procesarlo como misceláneo usando el nombre original como título (nota en Obsidian y video en YouTube). Si el nombre no incluye fecha `YYYY-MM-DD`, usar la fecha de modificación del archivo. Eliminar `OTR` de `config.json` y de toda la lógica interna.

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
