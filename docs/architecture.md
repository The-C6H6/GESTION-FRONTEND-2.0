# Arquitectura de ESIQIE-DICTÁMENES

## Objetivo del esqueleto

La aplicación es un frontend Flet web con navegación declarativa y sesión en memoria. La autenticación, la consulta de alumnos inscritos, la consulta de materias reprobadas y la creación de dictámenes usan el backend real. Registro, lectura, modificación y eliminación de dictámenes, además de la generación PDF, permanecen en modo demostración. Los siguientes adaptadores HTTP podrán sustituir a los demo sin cambiar las vistas.

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
    ├── HTTP: login, enrolled-student, failed-subject and ruling-create APIs
    └── Demo: remaining modules and PDF
```

- `core/` compone rutas, sesión, tema y servicios compartidos.
- `features/` agrupa modelos, contratos, controladores y vistas por caso de uso.
- `infrastructure/demo/` implementa contratos con datos en memoria.
- `infrastructure/http/` centraliza el cliente asíncrono, los adaptadores reales y los tokens efímeros.
- `shared/components/` contiene controles visuales reutilizables, sin reglas de negocio.
- Las vistas dependen de controladores, nunca de adaptadores concretos.

## Navegación y sesión

`ft.Router` declara `/login` como ruta pública. El resto de las rutas se renderiza dentro de un layout privado con navegación lateral y encabezado común. Si no existe una sesión en memoria, el layout redirige a `/login`. Cerrar sesión borra ese estado y vuelve al acceso.

La sesión es deliberadamente efímera. `ApiAuthRepository` envía las credenciales al backend, valida `access_token` y `refresh_token` y crea una sesión no demo. La respuesta actual no incluye identidad ni permisos, por lo que el frontend conserva el nombre introducido y usa `is_admin=False` hasta integrar `/api/auth/me`.

`AuthTokenStore` mantiene ambos tokens únicamente en memoria. `ApiClient` consulta el access token para construir los headers Bearer de inscritos y reprobados. El cierre de sesión manual limpia el almacén antes de abandonar el área privada. Una respuesta `401` también borra ambos tokens, invalida la sesión Flet y redirige a `/login`. Una respuesta `403` conserva la sesión y se presenta como un mensaje controlado. `/api/auth/refresh` está documentado, pero todavía no se consume.

## Contratos para la API

- `LoginRepository`: autenticación con `username` y `password`.
- `UserRepository`: registro de `username`, `password` e `is_admin`; continúa con adaptador demo.
- `DictamenRepository`: búsqueda por boleta o año, consulta por clave, creación, modificación de `dictaminacion` y eliminación por claves; el adaptador demo conserva estas operaciones completas.
- `DictamenCreateRepository`: contrato enfocado para crear un dictamen; producción usa `ApiDictamenRepository`.
- `InscritoRepository`: consulta de un inscrito por boleta; usa `ApiInscritoRepository`.
- `ReprobadoRepository`: búsqueda de materias reprobadas; producción usa `ApiReprobadoRepository` y demo conserva el adaptador combinado.
- `PdfGenerator`: recibe `PdfRequest` y devuelve `GeneratedDocument`.

`core/settings.py` carga `.env` en tiempo de ejecución. Prefiere `API_BASE_URL`, acepta `IP_ADDRESS` por compatibilidad y requiere `RUTA_LOGIN`, `RUTA_VISUALIZAR_INSCRITOS`, `RUTA_REPROBADOS` y `RUTA_GENERAR_DICTAMEN`. La ruta de inscritos debe contener exactamente un marcador `{boleta}`; las rutas de reprobados y creación deben ser relativas y no pueden incluir host, query, fragmento ni marcadores. Las pruebas inyectan un mapping explícito y nunca dependen de `.env` ni del backend real.

`ApiClient` centraliza URL base, query parameters, timeout, JSON, headers, Bearer Token, estado esperado y traducción de errores. `ApiInscritoRepository` codifica la boleta en la ruta y convierte la respuesta completa de la API al modelo `Inscrito`. `ApiReprobadoRepository` envía la boleta únicamente como `?boleta=...`, valida la página completa (`total`, `skip`, `limit`, `items`) y valida cada elemento del transporte antes de mapear solo materia, periodo, boleta y nombre al dominio. `ApiDictamenRepository` envía un único `POST`, exige estado `201`, valida la respuesta completa y obtiene `Clave` exclusivamente del backend. Las vistas reciben errores de aplicación con mensajes comprensibles; no construyen requests ni muestran códigos HTTP.

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

La composición ocurre en `core/services.py`. `build_services()` comparte un `ApiClient` y un `AuthTokenStore` entre `ApiAuthRepository`, `ApiInscritoRepository`, `ApiReprobadoRepository` y `ApiDictamenRepository`. El controlador conserva `DemoAlumnoRepository` y `DemoDictamenRepository` para compatibilidad y para lectura, modificación y eliminación simuladas, pero recibe por separado los repositorios HTTP de reprobados y creación. `build_demo_services()` continúa disponible para pruebas aisladas.

La búsqueda, modificación y eliminación reales de dictámenes, el registro de usuarios y la generación de PDF continúan fuera del alcance actual. El adaptador PDF futuro deberá basarse en las referencias de `referencias/` y consumir el `PdfRequest` ya separado del payload HTTP.
