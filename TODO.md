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
- [x] **Alias `clases`**: pipeline completo `procesar_clases.py` + `quitar_silencios.py` en secuencia.

### subir_clases.py (script nuevo)

- [x] **Subida a YouTube**: implementar un nuevo script `subir_clases.py` que tome
      los `.mp4` de `processed_videos_path` y los suba a YouTube via API v3.

### limpiar_clases.py

- [ ] **Borrar partes al limpiar**: cuando se limpia un video multipart
      (ej: `2026-03-31_4GDP.mp4`), también borrar los archivos `_p2`, `_p3`, etc.
      del `videos_dir`. Actualmente solo borra el original principal, dejando las
      partes huérfanas que `qs` vuelve a detectar como pendientes.

### subir_clases.py

- [ ] **Manejar token expirado**: cuando `creds.refresh()` falla con
      `RefreshError` (token expirado o revocado), borrar `youtube_token.json`
      automáticamente y re-autenticar en vez de crashear con traceback.

- [x] **Idioma del video**: agregar `defaultLanguage: "es-419"` al snippet
      de la subida para que YouTube lo detecte como Español (Latinoamérica)
      automáticamente.

- [x] **Idioma configurable por video**: el flag `-l` que se pasa a WhisperX
      para la transcripción debe propagarse también a `subir_clases.py` para setear
      `defaultLanguage` en YouTube. Como WhisperX usa códigos cortos (`es`, `en`, `it`)
      y YouTube usa BCP-47, hace falta un mapeo interno: español → `es-419`, inglés → `en`,
      y los idiomas comunes (italiano, portugués, francés, alemán, ruso, chino, japonés,
      etc.) → su BCP-47 correspondiente. Si no se pasa `-l`, se usa `es-419` como default.
      Implica propagar el flag por todo el pipeline (`pc → sc`) y desde
      `ProcesarClasesCompleto` en PowerShell.

### README.md

- [ ] **Documentar setup de YouTube**: agregar sección explicando cómo
      configurar la autenticación OAuth (crear proyecto en Google Cloud Console,
      descargar `client_secret.json`, primera ejecución que abre el navegador)
      y cómo funcionan las playlists en `config.json`.

### PowerShell

- [x] **Propagar flag `-l` al pipeline `clases`**: el flag `-l` (idioma de transcripción)
      solo existe en `procesar_clases.py` pero no se puede pasar desde el pipeline `clases`.
      Cuando WhisperX autodetecta mal el idioma (ej: detecta `jw` en vez de `es` en una
      clase en español), la transcripción crashea y no se genera ni el `.txt` ni la nota
      en Obsidian. Para forzar el idioma hay que correr `pc -l es` por separado, lo que
      rompe el flujo del pipeline completo. La solución es agregar el parámetro `-l` a
      `ProcesarClasesCompleto` en PowerShell y propagarlo a `pc`, igual que se hace con `-y`.

### Videos "otros" (todos los scripts)

- [x] **Eliminar código `OTR` y procesar "otros" por nombre original**: el código
      `OTR` es un comodín artificial que obliga a renombrar manualmente cualquier video
      que no sea una clase, siguiendo la convención `YYYY-MM-DD_OTR.mkv`, generando ruido
      y fricción innecesaria. Si el nombre del archivo no matchea ningún código conocido
      del `config.json`, procesarlo como "otro" conservando el nombre original del archivo
      como título (para la nota en Obsidian y para el video en YouTube), renombrando el
      archivo en disco a `YYYY-MM-DD_<nombre_original>.ext`. Si el nombre no incluye una
      fecha en formato `YYYY-MM-DD`, usar la fecha de modificación del archivo como
      metadato y como prefijo del renombrado. Eliminar `OTR` de `config.json` y de toda
      la lógica interna.

- [ ] **Fuzzy matching de códigos mal tipeados**: cuando un video cae en la categoría
      "otros" porque su código no matchea ninguno del `config.json`, chequear si el nombre
      del archivo se parece a algún código conocido (ej: `YYYY-MM-DD_AA3.mkv` cuando
      existe `AA2`). Si la similitud es alta, avisar al usuario antes de procesarlo como
      "otro": "¿este video está mal nombrado? el código no coincide exacto con `AA2`,
      querés renombrarlo?". No implementar todavía — dejar anotado para más adelante.

### UI

- [ ] **Rich**: Agregar colores a los menúes interactivos para simplificar la visualización de las distintas información que brinda el menú.

