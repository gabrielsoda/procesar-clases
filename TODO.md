# TODO — tuia-procesar-clases

## implementaciones Pendientes

### quitar_silencios.py

- [ ] **Eliminar el chequeo de `.txt`** en `detectar_pendientes()`. El criterio de
      "pendiente" debería ser solo: matchea el patrón `YYYY-MM-DD_NCOD.ext` y no
      tiene `.mp4` en `processed_videos_path`. El `.txt` no es necesario para recortar
      silencios; su uso quedará para cuando se implemente la subida a YouTube.

- [ ] **Unir partes automáticamente**: cuando se detectan `YYYY-MM-DD_NCOD.mkv` y
      `YYYY-MM-DD_NCOD_p2.mkv` (y eventuales `_p3`, etc.), recortarles silencios por
      separado y concatenarlos en un único `.mp4` final en `processed_videos_path`.
      El archivo de salida debería llamarse `YYYY-MM-DD_NCOD.mp4` (sin sufijo de parte).

- [ ] **Mostrar barra de progreso de auto-editor**: en `recortar_silencios()`, cambiar
      `capture_output=True` por dejar que auto-editor imprima directo a la terminal.
      Actualmente la salida queda capturada y no se ve el progreso durante el procesado.

### pyproject.toml

- [ ] **Actualizar campo deprecado**: cambiar `[tool.uv] dev-dependencies = []`
      por `[dependency-groups] dev = []` para eliminar el warning de uv.

### Commits pendientes

- [ ] Hacer el commit de esta sesión con todos los cambios actuales:
      `quitar_silencios.py`, `config.json`, `.gitignore`, `procesar_clases.py`
      (rename `video_extensions` → `file_extensions`), `README.md`, `pyproject.toml`.

