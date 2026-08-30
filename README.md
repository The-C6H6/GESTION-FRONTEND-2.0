# ESIQIE-DICTÁMENES

Frontend Flet para gestionar dictámenes de estudiantes de ESIQIE. La autenticación, la consulta de alumnos inscritos, sus materias reprobadas, y la creación, búsqueda paginada, modificación y eliminación de dictámenes consumen la API real. El registro de usuarios y la generación PDF continúan con adaptadores de demostración; la autenticación nunca recurre a datos demo.

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
- `RUTA_AUTENTICACION`, para la identidad autenticada de `/api/auth/me`;
- `RUTA_REFRESH`, para renovar la sesión mediante `/api/auth/refresh`;
- `RUTA_VISUALIZAR_INSCRITOS`, con el marcador `{boleta}`;
- `RUTA_REPROBADOS`, como ruta relativa sin parámetros, query ni fragmento;
- `RUTA_GENERAR_DICTAMEN`, como ruta relativa sin parámetros, query, fragmento ni marcadores.
- `RUTA_LECTURA_DICTAMINACIONES`, como ruta relativa sin parámetros, query, fragmento ni marcadores.
- `RUTA_MODIFICAR_DICTAMEN`, como ruta relativa con exactamente un marcador `{clave}` y sin query ni fragmento.
- `RUTA_ELIMINAR`, como ruta relativa sin parámetros, query, fragmento ni marcadores.

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

- El login real ejecuta `POST /api/auth/login` y después `GET /api/auth/me`. La identidad y el rol proceden exclusivamente de `/auth/me`; no se decodifica el JWT ni se infieren permisos por nombre de usuario.
- Access token, refresh token y usuario autenticado viven juntos en una única sesión efímera en memoria. Una respuesta `401` autenticada coordina una sola renovación y repite la solicitud original una vez; no existe bucle de reintentos.
- Un refresh rechazado, inválido o seguido por otro `401` elimina la sesión completa. Un timeout, fallo de conexión o error `5xx` durante el refresh conserva una sesión ya establecida para que una operación posterior pueda intentarlo de nuevo.
- Si la sesión cambia mientras una renovación está en curso, la operación anterior se descarta sin reutilizar ni borrar la sesión nueva.
- Búsqueda de inscritos, consulta paginada de materias reprobadas, y creación, búsqueda paginada, modificación y eliminación de dictámenes mediante API.
- La búsqueda real de dictámenes admite únicamente número de boleta o año, usa páginas del servidor de 100 registros y conserva el último resultado correcto si falla una navegación.
- La modificación exige seleccionar exactamente un resultado, permite editar solo `Dictaminación` y conserva el filtro, la página y los demás registros tras un `PUT` correcto.
- La eliminación admite uno o varios resultados seleccionados, exige confirmación explícita y envía únicamente sus claves en un `DELETE` bulk. Tras el éxito vuelve a consultar el filtro y retrocede a la última página válida cuando es necesario.
- El tipo seleccionado determina la única fuente de búsqueda: `Alumno inscrito` usa `/api/inscritos/{boleta}` y `Alumno reprobado` usa `/api/reprobados?boleta=<boleta>`, sin fallback entre endpoints.
- El rol de `/auth/me` gobierna la navegación y las vistas. Los usuarios normales conservan las consultas de inscritos, materias reprobadas y dictámenes, pero no ven ni pueden ejecutar creación, modificación, eliminación o registro de usuarios; los controladores vuelven a exigir permisos antes de cualquier mutación.
- Cierre de sesión manual, navegación privada y página 404. Una expiración terminal también invalida el área privada y vuelve al login, mientras un `403` conserva la sesión y muestra un error controlado.
- Preparación separada del contexto PDF, incluido el nombre del director, sin generar todavía un archivo real después de crear el dictamen.
- Presentación de los datos académicos del inscrito y selección automática de materias reprobadas elegibles obtenidas de la API.
- Registro simulado de usuarios estándar o administradores, protegido para administradores autenticados.

La arquitectura y los límites están en [docs/architecture.md](docs/architecture.md). Los wireframes acordados están en [docs/ui-wireframes.md](docs/ui-wireframes.md).
