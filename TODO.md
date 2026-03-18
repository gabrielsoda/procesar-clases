# TODO — tuia-procesar-clases

## implementaciones Pendientes

### quitar_silencios.py

- [x] **Eliminar el chequeo de `.txt`** en `detectar_pendientes()`. El criterio de
      "pendiente" debería ser solo: matchea el patrón `YYYY-MM-DD_NCOD.ext` y no
      tiene `.mp4` en `processed_videos_path`. El `.txt` no es necesario para recortar
      silencios; su uso quedará para cuando se implemente la subida a YouTube.

- [x] **Unir partes automáticamente**: cuando se detectan `YYYY-MM-DD_NCOD.mkv` y
      `YYYY-MM-DD_NCOD_p2.mkv` (y eventuales `_p3`, etc.), recortarles silencios por
      separado y concatenarlos en un único `.mp4` final en `processed_videos_path`.
      El archivo de salida debería llamarse `YYYY-MM-DD_NCOD.mp4` (sin sufijo de parte).

- [x] **Mostrar barra de progreso de auto-editor**: en `recortar_silencios()`, cambiar
      `capture_output=True` por dejar que auto-editor imprima directo a la terminal.
      Actualmente la salida queda capturada y no se ve el progreso durante el procesado.

### pyproject.toml

- [x] **Actualizar campo deprecado**: cambiar `[tool.uv] dev-dependencies = []`
      por `[dependency-groups] dev = []` para eliminar el warning de uv.

### PowerShell

- [x] **Alias para `quitar_silencios.py`**: agregar un alias `qs` en el
      perfil de PowerShell, como ya existe `pc` para `procesar_clases.py`.
- [x] **Alias para `quitar_silencios.py` + `procesar_clases.py`**: agregar un alias `pcqs` en el
      perfil de PowerShell que combine ambas funciones.

### subir_clases.py (script nuevo)

- [ ] **Subida a YouTube**: implementar un nuevo script `subir_clases.py` que tome
      los `.mp4` de `processed_videos_path` y los suba a YouTube via API v3.
      Flujo previsto:
        - Detectar pendientes: `.mp4` en `processed_videos_path` con `.txt` asociado
          y sin `.uploaded` marker
        - OAuth 2.0 con `google-auth` + `google-api-python-client`
        - Subir video con título, descripción y categoría según `config.json`
        - Asignar a playlist según código de materia
        - Subir subtítulos desde el `.txt` de transcripción
        - Crear archivo `.uploaded` como marker de completado

### UI
- [ ] **Rich**: Agregar colores a los menúes interactivos para simplificar la visualización de las distintas información que brinda el menú.

