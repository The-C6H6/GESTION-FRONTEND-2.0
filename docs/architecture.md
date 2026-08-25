# Arquitectura de ESIQIE-DICTÁMENES

## Objetivo del esqueleto

La aplicación es un frontend Flet web con navegación declarativa y sesión en memoria. La autenticación y la consulta de alumnos inscritos usan el backend real; registro, reprobados, dictámenes y generación PDF permanecen en modo demostración. Los siguientes adaptadores HTTP podrán sustituir a los demo sin cambiar las vistas.

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
    ├── HTTP: login and enrolled-student API
    └── Demo: remaining modules and PDF
```

- `core/` compone rutas, sesión, tema y servicios compartidos.
- `features/` agrupa modelos, contratos, controladores y vistas por caso de uso.
- `infrastructure/demo/` implementa contratos con datos en memoria.
- `infrastructure/http/` centraliza el cliente asíncrono, el login real y los tokens efímeros.
- `shared/components/` contiene controles visuales reutilizables, sin reglas de negocio.
- Las vistas dependen de controladores, nunca de adaptadores concretos.

## Navegación y sesión

`ft.Router` declara `/login` como ruta pública. El resto de las rutas se renderiza dentro de un layout privado con navegación lateral y encabezado común. Si no existe una sesión en memoria, el layout redirige a `/login`. Cerrar sesión borra ese estado y vuelve al acceso.

La sesión es deliberadamente efímera. `ApiAuthRepository` envía las credenciales al backend, valida `access_token` y `refresh_token` y crea una sesión no demo. La respuesta actual no incluye identidad ni permisos, por lo que el frontend conserva el nombre introducido y usa `is_admin=False` hasta integrar `/api/auth/me`.

`AuthTokenStore` mantiene ambos tokens únicamente en memoria. `ApiClient` consulta el access token para construir los headers Bearer del login y de inscritos. El cierre de sesión manual limpia el almacén antes de abandonar el área privada. Una respuesta `401` también borra ambos tokens, invalida la sesión Flet y redirige a `/login`. `/api/auth/refresh` está documentado, pero todavía no se consume.

## Contratos para la API

- `LoginRepository`: autenticación con `username` y `password`.
- `UserRepository`: registro de `username`, `password` e `is_admin`; continúa con adaptador demo.
- `DictamenRepository`: búsqueda por boleta o año, consulta por clave, creación, modificación de `dictaminacion` y eliminación por claves.
- `InscritoRepository`: consulta de un inscrito por boleta; usa `ApiInscritoRepository`.
- `ReprobadoRepository`: búsqueda de materias reprobadas; continúa con adaptador demo.
- `PdfGenerator`: recibe `PdfRequest` y devuelve `GeneratedDocument`.

`core/settings.py` carga `.env` en tiempo de ejecución. Prefiere `API_BASE_URL`, acepta `IP_ADDRESS` por compatibilidad y requiere `RUTA_LOGIN` y `RUTA_VISUALIZAR_INSCRITOS`. La ruta de inscritos debe contener exactamente un marcador `{boleta}`. Las pruebas inyectan un mapping explícito y nunca dependen de `.env` ni del backend real.

`ApiClient` centraliza URL base, timeout, JSON, headers, Bearer Token y traducción de errores. `ApiInscritoRepository` codifica la boleta en la ruta y convierte la respuesta completa de la API al modelo `Inscrito`. Las vistas reciben errores de aplicación con mensajes comprensibles; no construyen requests ni muestran códigos HTTP.

## Datos de API y datos de PDF

`DictamenCreate` contiene únicamente los campos previstos para la API. El nombre del director, la fecha de sesión y las materias elegibles pertenecen a `PdfRequest`, por lo que no contaminan el payload de creación. `fecha_sesion` se conserva como `date` y el adaptador PDF debe usar el formateador compartido para producir textos como `11 DE DICIEMBRE`, sin año. Al modificar, la interfaz solo construye `DictamenUpdate(dictaminacion=...)`; clave, boleta y año permanecen de solo lectura.

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

## Sustitución futura de adaptadores

La composición ocurre en `core/services.py`. `build_services()` comparte un `ApiClient` y un `AuthTokenStore` entre `ApiAuthRepository` y `ApiInscritoRepository`. El controlador de reprobados conserva un `DemoAlumnoRepository` independiente, y los demás módulos siguen en demostración. `build_demo_services()` continúa disponible para pruebas aisladas.

El siguiente adaptador recomendado es la consulta de reprobados, porque alimenta la selección de materias antes de conectar la creación real de dictámenes. Debe reutilizar `ApiClient` y sus errores en lugar de duplicar requests. La generación real seguirá el mismo patrón con una implementación de `PdfGenerator` basada en las referencias de `referencias/`.
