# docstring del módulo

# imports

# constantes (CONFIG_PATH, regex VIDEO_PROCESADO)

# configuración
def cargar_config():
    pass
# autenticación YouTube
def autenticar_youtube(config) -> youtube service object:
    pass
# detección de pendientes
def detectar_pendientes(processed_dir, codigos_validos) -> list[dict]:
    pass
# preview interactivo
def mostrar_preview_y_seleccionar(pendientes, config, auto_yes) -> list[dict] | None:
    pass
# subida de video
def subir_video(youtube, video_path, titulo, config) -> video_id | None:
    pass
# asignación a playlist
def agregar_a_playlist(youtube, video_id, playlist_id) -> bool:
    pass
# flujo principal
def procesar(config, auto_yes):
    pass
# entrypoint
if __name__ == "__main__": ...