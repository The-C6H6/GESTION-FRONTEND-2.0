# Arquitectura de ESIQIE-DICTÁMENES

## Objetivo del esqueleto

La aplicación es un frontend Flet web con navegación declarativa y sesión en memoria. La autenticación, el registro de usuarios, la consulta de alumnos inscritos, la consulta de materias reprobadas, y la creación, búsqueda paginada, modificación y eliminación de dictámenes usan el backend real. Solo la generación PDF permanece en modo demostración; no existe autenticación demo ni fallback de identidad.

## Capas y dependencias

```text
Flet views
    │
    ▼
Feature controllers
    │
    ├── repository contracts
    └── PDF contract
             ▲
             │
Infrastructure adapters
    ├── HTTP: login/identity/refresh, user-registration, enrolled-student, failed-subject, ruling-create/search/update/delete APIs
    └── Demo: PDF and compatibility repositories
```

- `core/` compone rutas, sesión, tema y servicios compartidos.
- `features/` agrupa modelos, contratos, controladores y vistas por caso de uso.
- `infrastructure/demo/` implementa contratos con datos en memoria.
- `infrastructure/http/` centraliza el cliente asíncrono y los adaptadores reales; el estado autenticado pertenece a `core/session.py`.
- `shared/components/` contiene controles visuales reutilizables, sin reglas de negocio.
- Las vistas dependen de controladores, nunca de adaptadores concretos.

## Navegación y sesión

`ft.Router` declara `/login` como ruta pública. El resto de las rutas se renderiza dentro de un layout privado con navegación lateral y encabezado común. Si no existe una sesión activa en memoria, el layout redirige a `/login`. Las rutas `/usuarios/nuevo` y `/dictamenes/eliminar` requieren un administrador y redirigen a un usuario normal al dashboard antes de renderizar el contenido protegido. Cerrar sesión borra el estado autenticado completo y vuelve al acceso.

La sesión es deliberadamente efímera. `AuthSessionStore` conserva en una única instancia compartida el access token, el refresh token y un `AuthenticatedUser` tipado. Ninguno de los tokens se incluye en representaciones ni logs. El login ejecuta `POST /api/auth/login` sin Bearer, inicia una sesión pendiente con el par de tokens y después solicita `GET /api/auth/me`. Solo una identidad activa y completamente validada convierte esa sesión pendiente en una sesión publicable. `id`, `username`, `is_active` e `is_admin` proceden exclusivamente de `/auth/me`; el frontend no decodifica JWTs ni deriva roles de nombres de usuario.

`ApiClient` usa el access token de esa misma sesión para construir los headers Bearer. Ante el primer `401` de una solicitud autenticada coordina una renovación single-flight por sesión y token expirado: envía una sola vez `POST /api/auth/refresh` sin Bearer, rota el par completo y repite exactamente una vez el método, ruta, cuerpo, parámetros y estado esperado de la solicitud original. Un refresh `401`/`403`, la ausencia de refresh token, un payload inválido o un segundo `401` eliminan tokens e identidad juntos. Los timeouts, fallos de conexión y respuestas `5xx` del refresh conservan una sesión ya establecida y no repiten la operación original. Un `403` normal también conserva la sesión y se presenta como un mensaje controlado.

La coordinación captura además la instancia de sesión que originó la solicitud. Si durante el refresh otra autenticación la sustituye, la operación obsoleta termina con un error seguro, sin repetir la petición con credenciales nuevas y sin limpiar la sesión sustituta. Los refreshes concurrentes comparten trabajo únicamente cuando pertenecen a la misma instancia y al mismo access token.

## Contratos para la API

- `LoginRepository`: autenticación con `username` y `password`.
- `AuthenticatedUser`: identidad tipada devuelta por `/api/auth/me`; es la única fuente de estado activo y rol.
- `UserRepository`: registro de `username`, `password` e `is_admin`; producción usa `ApiUserRepository`.
- `DictamenRepository`: búsqueda por boleta o año, consulta por clave, creación, modificación de `dictaminacion` y eliminación por claves; el adaptador demo conserva estas operaciones completas.
- `DictamenCreateRepository`: contrato enfocado para crear un dictamen; producción usa `ApiDictamenRepository`.
- `DictamenSearchRepository`: contrato enfocado para consultar una página de dictámenes con un único filtro confirmado; producción reutiliza `ApiDictamenRepository`.
- `DictamenUpdateRepository`: contrato enfocado para modificar únicamente la dictaminación de un registro existente; producción reutiliza `ApiDictamenRepository`.
- `DictamenDeleteRepository`: contrato enfocado para eliminar una o varias claves; producción reutiliza `ApiDictamenRepository`.
- `InscritoRepository`: consulta de un inscrito por boleta; usa `ApiInscritoRepository`.
- `ReprobadoRepository`: búsqueda de materias reprobadas; producción usa `ApiReprobadoRepository` y demo conserva el adaptador combinado.
- `PdfGenerator`: recibe `PdfRequest` y devuelve `GeneratedDocument`.

`core/settings.py` carga `.env` en tiempo de ejecución. Prefiere `API_BASE_URL`, acepta `IP_ADDRESS` por compatibilidad y requiere `RUTA_LOGIN`, `RUTA_AUTENTICACION`, `RUTA_REFRESH`, `RUTA_NUEVO_USUARIO`, `RUTA_VISUALIZAR_INSCRITOS`, `RUTA_REPROBADOS`, `RUTA_GENERAR_DICTAMEN`, `RUTA_LECTURA_DICTAMINACIONES`, `RUTA_MODIFICAR_DICTAMEN` y `RUTA_ELIMINAR`. Las rutas de identidad, renovación y registro son rutas estáticas relativas: no aceptan host, query, fragmento ni marcadores. La ruta de inscritos debe contener exactamente un marcador `{boleta}`; las rutas de reprobados, creación, lectura y eliminación de dictámenes deben ser relativas y no pueden incluir host, query, fragmento ni marcadores. La ruta de modificación debe ser relativa y contener exactamente un marcador `{clave}`. Las pruebas inyectan un mapping explícito y nunca dependen de `.env` ni del backend real.

`ApiClient` centraliza URL base, query parameters, timeout, JSON, headers, Bearer Token, estado esperado, renovación de sesión y traducción de errores. Solo reintenta una solicitud autenticada después de su primer `401`; no reintenta timeouts, fallos de conexión, errores de servidor ni mutaciones por otra causa. `ApiUserRepository` envía un `POST` autenticado con exactamente `username`, `password` e `is_admin`, exige `201` y valida por completo la identidad creada antes de confirmar éxito. Solo el detalle backend conocido de nombre duplicado se traduce al mensaje específico; los demás errores conservan la traducción centralizada. `ApiInscritoRepository` codifica la boleta en la ruta y convierte la respuesta completa de la API al modelo `Inscrito`. `ApiReprobadoRepository` envía la boleta únicamente como `?boleta=...`, valida la página completa (`total`, `skip`, `limit`, `items`) y valida cada elemento del transporte antes de mapear solo materia, periodo, boleta y nombre al dominio. `ApiDictamenRepository` conserva el `POST` de creación, consulta `GET /api/dictaminaciones` con un único filtro `boleta` o `anio`, `skip` y `limit=100`, modifica mediante un único `PUT /api/dictaminaciones/{clave}` y elimina mediante un único `DELETE` a la ruta configurada. El `PUT` envía exactamente `{"Dictaminacion": "..."}`; el `DELETE` envía únicamente `{"claves": [...]}`. Ambos validan la respuesta antes de confirmar éxito. Las vistas reciben errores de aplicación con mensajes comprensibles; no construyen requests ni muestran códigos HTTP.

La vista de búsqueda conserva por separado los filtros editables y el filtro confirmado. Una nueva búsqueda siempre solicita la página 1 y reemplaza el resultado anterior; `Anterior` y `Siguiente` reutilizan el filtro confirmado sin acumular filas. Si una navegación falla, se mantiene la última página correcta. El guard retenido evita requests concurrentes y el loading bloquea criterios, consulta, paginación y acciones visibles. Solo los detalles conocidos de ausencia de dictámenes en un `400` se traducen a una página vacía neutral; otros `400` mantienen el error de validación.

La modificación forma parte de la misma vista paginada. El usuario marca filas, pero debe confirmar exactamente una para abrir el editor. La clave, boleta, alumno, fecha y año se presentan como texto de solo lectura; el único campo editable es `Dictaminación`. Búsqueda y guardado comparten el mismo guard. Tras un `PUT` correcto se sustituye únicamente el objeto de la página actual, sin cambiar filtro, página, rango ni filas no relacionadas. Cancelar, enviar texto vacío o conservar el valor normalizado no genera un request. No existe actualización optimista ni reintento automático ante un resultado ambiguo.

La eliminación reutiliza la selección múltiple y las entidades `Dictamen` de la misma tabla. El botón destructivo siempre abre un diálogo de confirmación; cancelar o no seleccionar no genera requests. Búsqueda, modificación y eliminación comparten el request gate. Tras un `DELETE` confirmado se limpia la selección, se vuelve a consultar el filtro confirmado y se conserva la página mientras siga siendo válida; si desaparece la última página, se solicita la nueva última página. Un timeout o fallo de conexión no provoca retry ni eliminación local, y un `404` no se interpreta como éxito parcial.

## Autorización por rol

`AuthSessionStore.require_admin()` exige una identidad activa con `is_admin=True`. `UserController` y `DictamenController` reciben ese guard desde la composición y lo ejecutan antes de registrar usuarios o crear, modificar y eliminar dictámenes. Los handlers de las vistas lo repiten antes de abrir estado de edición o confirmación y antes de delegar, por lo que una callback invocada directamente tampoco alcanza un repositorio de mutación. `UserController` refleja localmente el mínimo backend de seis caracteres y devuelve un mensaje específico sin alcanzar el repositorio. El formulario de registro usa el request gate compartido para admitir un solo envío concurrente, deshabilita la acción mientras espera y solo limpia contraseña y confirmación después de una respuesta válida. El backend conserva la autoridad final: un `403` se traduce a un mensaje seguro y no elimina la sesión.

La navegación lateral, el dashboard y las vistas consultan únicamente `session.current_user.is_admin`. Un administrador conserva todas las operaciones. Un usuario normal mantiene las consultas de inscritos, materias reprobadas y dictámenes; `/dictamenes/nuevo` se presenta como consulta de alumnos y oculta director, fecha de sesión, dictaminación, preparación PDF y creación. La consulta de dictámenes conserva filtros, paginación y resultados, pero elimina selección, modificación y eliminación. Los resultados de inscritos tampoco ofrecen crear dictamen.

## Datos de API y datos de PDF

`DictamenCreate` contiene únicamente los campos previstos para la API: boleta, nombre, fecha de emisión, año y dictaminación. La fecha se obtiene al crear, se conserva como `date` en el dominio y se serializa como ISO `YYYY-MM-DD`; `Clave` nunca forma parte de la solicitud. El nombre del director, la fecha de sesión y las materias elegibles pertenecen a `PdfRequest`, por lo que no contaminan el payload de creación. `fecha_sesion` se conserva como `date` y el adaptador PDF debe usar el formateador compartido para producir textos como `11 DE DICIEMBRE`, sin año. Crear un dictamen prepara este contexto tipado, pero no invoca al generador PDF. Al modificar, la interfaz solo construye `DictamenUpdate(dictaminacion=...)`; clave, boleta y año permanecen de solo lectura.

El generador demo devuelve un nombre de archivo, `is_simulation=True` y una vista previa del párrafo de sesión, pero ningún contenido binario. Esto evita ofrecer una descarga que aparente ser un PDF válido.

## Regla de periodos

El periodo inicial se obtiene de la fecha local:

- Enero-junio: `<año>2`.
- Julio-diciembre: `<año siguiente>1`.

Una materia reprobada se agrega obligatoriamente al contexto del PDF cuando:

```text
19 <= int(periodo_actual) - int(periodo_reprobada) < 29
```

La selección se calcula en el controlador y la vista solo la presenta. Las materias elegibles no tienen un control para desmarcarlas.

El dropdown determina la fuente de forma explícita en `DictamenController`: `Alumno inscrito` consulta únicamente `GET /api/inscritos/{boleta}` y `Alumno reprobado` consulta únicamente `GET /api/reprobados?boleta=<boleta>`. No existe fallback ni comprobación cruzada entre repositorios. Un alumno reprobado se representa como `AlumnoDictaminable` usando los datos comunes de los propios items, sin fabricar un `Inscrito`; una página vacía produce el estado controlado de no encontrado. Después se aplica la regla de periodos a sus materias. Un guard retenido por el componente impide consultas concurrentes duplicadas y restaura siempre el estado de carga. Al cambiar boleta, origen o periodo se invalida la selección anterior para impedir que un dictamen use datos que ya no corresponden a los criterios visibles.

## Sustitución futura de adaptadores

La composición ocurre en `core/services.py`. `build_services()` comparte un `ApiClient` y un único `AuthSessionStore` entre `ApiAuthRepository`, `ApiUserRepository`, los demás adaptadores HTTP y los guards de los controladores. El controlador conserva `DemoAlumnoRepository` y `DemoDictamenRepository` para compatibilidad, pero recibe por separado los repositorios HTTP enfocados de inscritos, reprobados, creación, búsqueda, modificación y eliminación. Las pruebas construyen sus propias sesiones y servicios no conectados; producción no ofrece login, sesión ni registro de usuarios demo.

La generación real de PDF continúa fuera del alcance actual. El adaptador PDF futuro deberá basarse en las referencias de `referencias/` y consumir el `PdfRequest` ya separado del payload HTTP.
