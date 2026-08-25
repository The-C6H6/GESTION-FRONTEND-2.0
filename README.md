# ESIQIE-DICTÁMENES

Frontend Flet para gestionar dictámenes de estudiantes de ESIQIE. El login y la consulta de alumnos inscritos consumen la API real; los demás casos de uso continúan con adaptadores de demostración.

## Requisitos

- Windows 11.
- Python 3.13 o compatible.
- `uv`.

## Preparación

```powershell
uv venv
uv sync
```

`uv` crea y mantiene `.venv`. No es necesario activarlo para usar los comandos siguientes.

## Configuración de la API

La ejecución local carga `.env` mediante `python-dotenv`. Debe definir:

- `API_BASE_URL` o, por compatibilidad, `IP_ADDRESS`;
- `RUTA_LOGIN`;
- `RUTA_VISUALIZAR_INSCRITOS`, con el marcador `{boleta}`.

Consulta `.env.example` para las rutas disponibles. No incluyas credenciales ni tokens en archivos versionados.

## Ejecutar pruebas

```powershell
uv run pytest
```

## Ejecutar la aplicación web

```powershell
uv run flet run --web --port 8501 src/main.py
```

Abre `http://127.0.0.1:8501`. El backend configurado debe estar disponible para iniciar sesión con credenciales válidas.

## Alcance actual

- Login y búsqueda de inscritos mediante API, con un mismo token Bearer efímero en memoria.
- Cierre de sesión manual o automático ante una respuesta `401`, navegación privada y página 404.
- Búsqueda, creación, eliminación y modificación simulada de dictámenes.
- Simulación del contexto de generación PDF, incluido el nombre del director.
- Presentación de los datos académicos del inscrito y selección automática simulada de materias reprobadas elegibles.
- Registro simulado de usuarios estándar o administradores.

La arquitectura y los límites están en [docs/architecture.md](docs/architecture.md). Los wireframes acordados están en [docs/ui-wireframes.md](docs/ui-wireframes.md).
