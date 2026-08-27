# ESIQIE-DICTÁMENES

Frontend Flet para gestionar dictámenes de estudiantes de ESIQIE. El login, la consulta de alumnos inscritos, sus materias reprobadas, y la creación, búsqueda paginada y modificación de dictámenes consumen la API real; los demás casos de uso continúan con adaptadores de demostración.

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
- `RUTA_VISUALIZAR_INSCRITOS`, con el marcador `{boleta}`;
- `RUTA_REPROBADOS`, como ruta relativa sin parámetros, query ni fragmento;
- `RUTA_GENERAR_DICTAMEN`, como ruta relativa sin parámetros, query, fragmento ni marcadores.
- `RUTA_LECTURA_DICTAMINACIONES`, como ruta relativa sin parámetros, query, fragmento ni marcadores.
- `RUTA_MODIFICAR_DICTAMEN`, como ruta relativa con exactamente un marcador `{clave}` y sin query ni fragmento.

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

- Login, búsqueda de inscritos, consulta paginada de materias reprobadas, y creación, búsqueda paginada y modificación de dictámenes mediante API, con un mismo token Bearer efímero en memoria.
- La búsqueda real de dictámenes admite únicamente número de boleta o año, usa páginas del servidor de 100 registros y conserva el último resultado correcto si falla una navegación.
- La modificación exige seleccionar exactamente un resultado, permite editar solo `Dictaminación` y conserva el filtro, la página y los demás registros tras un `PUT` correcto.
- El tipo seleccionado determina la única fuente de búsqueda: `Alumno inscrito` usa `/api/inscritos/{boleta}` y `Alumno reprobado` usa `/api/reprobados?boleta=<boleta>`, sin fallback entre endpoints.
- Cierre de sesión manual o automático ante una respuesta `401`, navegación privada y página 404.
- Eliminación simulada de dictámenes.
- Preparación separada del contexto PDF, incluido el nombre del director, sin generar todavía un archivo real después de crear el dictamen.
- Presentación de los datos académicos del inscrito y selección automática de materias reprobadas elegibles obtenidas de la API.
- Registro simulado de usuarios estándar o administradores.

La arquitectura y los límites están en [docs/architecture.md](docs/architecture.md). Los wireframes acordados están en [docs/ui-wireframes.md](docs/ui-wireframes.md).
