# Diseño de integración del login con la API

**Fecha:** 2026-08-24  
**Estado:** Aprobado para planificación

## Objetivo

Conectar la pantalla de acceso existente con `POST /api/auth/login` mediante una capa HTTP asíncrona reutilizable, sin colocar lógica de red en los controles Flet y sin integrar todavía los demás endpoints ni la generación real de PDF.

## Alcance

Esta etapa incluye:

- carga de la URL base y la ruta de login desde variables de entorno;
- un cliente HTTP reutilizable con timeout, JSON, headers y traducción de errores;
- un adaptador de autenticación que implemente únicamente el login real;
- almacenamiento efímero de los tokens en memoria;
- envío automático del Bearer Token en futuras peticiones realizadas por el mismo cliente;
- limpieza de los tokens al cerrar sesión;
- conexión del formulario Flet existente con la API;
- pruebas unitarias sin depender del backend real.

Esta etapa no incluye:

- consumo de `/api/auth/me` o `/api/auth/refresh`;
- registro real de usuarios;
- integración HTTP de dictámenes, inscritos o reprobados;
- persistencia de sesión entre reinicios;
- generación o modificación de archivos PDF;
- cambios en el backend o en la base de datos;
- rediseño de las pantallas.

`RUTA_REFRESH_TOKEN` queda documentada en `.env.example` para una etapa posterior, pero no se consume en esta implementación.

## Contrato verificado de la API

El esquema OpenAPI local expone el siguiente contrato:

```text
POST /api/auth/login
Content-Type: application/json

{
  "username": "usuario",
  "password": "contraseña"
}
```

La respuesta exitosa contiene:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer"
}
```

La respuesta no contiene el nombre del usuario ni su indicador de administrador. La sesión del frontend conservará el nombre enviado en el formulario y usará `is_admin=False` hasta que una etapa posterior integre `/api/auth/me`. No se decodificará el JWT para inferir permisos sin validarlo.

## Arquitectura

```text
LoginView
    │
    ▼
AuthController
    │ LoginRepository
    ▼
ApiAuthRepository
    ├── ApiClient ─────────────► FastAPI
    └── AuthTokenStore
```

La dirección de dependencias se mantiene como:

```text
UI → controladores → contratos → adaptadores de infraestructura
```

Las vistas no importarán `httpx`, configuración ni adaptadores concretos.

## Componentes

### Configuración

`core/settings.py` definirá `ApiSettings` con:

- `base_url: str`;
- `login_path: str`;
- `timeout_seconds: float`.

La carga de producción llamará a `python-dotenv` para incorporar `.env` al entorno del proceso sin exponer su contenido. Para las pruebas se podrá inyectar un mapping explícito, evitando leer archivos locales.

La URL base seguirá esta precedencia:

1. `API_BASE_URL`;
2. `IP_ADDRESS`, como nombre compatible con configuraciones anteriores.

`RUTA_LOGIN` será obligatoria. La configuración no incluirá URLs predeterminadas hardcodeadas. Un valor ausente o inválido producirá un error de configuración traducible para la interfaz.

### Contratos por responsabilidad

El contrato actual de autenticación mezcla login y registro. Se separará en:

- `LoginRepository`, consumido por `AuthController`;
- `UserRepository`, consumido por `UserController`.

`DemoAuthRepository` seguirá satisfaciendo ambos contratos estructuralmente. `ApiAuthRepository` implementará solo `LoginRepository`, evitando métodos ficticios o excepciones de “no implementado”.

### Almacenamiento de tokens

`AuthTokenStore` conservará `access_token` y `refresh_token` únicamente en memoria. Sus responsabilidades serán:

- reemplazar ambos tokens después de un login exitoso;
- devolver el access token al cliente HTTP sin exponer el refresh token;
- limpiar ambos valores en un intento fallido y al cerrar sesión;
- impedir que los secretos aparezcan en su representación textual.

No se usarán archivos, preferencias, `SecureStorage` ni variables globales. La persistencia queda fuera del alcance.

### Cliente HTTP

`ApiClient` recibirá `ApiSettings`, `AuthTokenStore` y opcionalmente un `httpx.AsyncBaseTransport` para pruebas. Expondrá una operación asíncrona reutilizable para realizar peticiones JSON.

El cliente será responsable de:

- resolver rutas relativas contra `base_url`;
- aplicar el timeout configurado;
- establecer `Accept: application/json` y `Content-Type: application/json` cuando corresponda;
- adjuntar `Authorization: Bearer <token>` cuando el almacén contenga un access token;
- procesar respuestas JSON;
- cerrar cada `httpx.AsyncClient` mediante un context manager;
- transformar errores técnicos en errores de aplicación.

Crear el cliente HTTP interno por petición evita recursos abiertos en esta primera etapa. La interfaz pública permitirá incorporar pooling más adelante sin cambiar las vistas ni los repositorios.

### Adaptador de autenticación

`ApiAuthRepository.login(username, password)` realizará esta secuencia:

1. limpiar cualquier token anterior;
2. enviar exclusivamente `username` y `password` al `login_path`;
3. validar que la respuesta sea un objeto JSON;
4. validar que `access_token` y `refresh_token` sean strings no vacíos;
5. almacenar ambos tokens;
6. devolver `Session(username=username, is_admin=False, is_demo=False)`.

Las contraseñas y tokens no se incluirán en mensajes, excepciones ni logs.

### Composición de servicios

`core/services.py` conservará `build_demo_services()` para pruebas y demostraciones. Añadirá una composición de producción donde:

- `AuthController` use `ApiAuthRepository`;
- `UserController` continúe con `DemoAuthRepository`;
- dictámenes, alumnos y PDF continúen usando adaptadores demo;
- todos los servicios de una sesión Flet compartan un único `AuthTokenStore`.

La aplicación usará esta composición híbrida por defecto. Esto integra únicamente el login y mantiene explícitamente el resto del producto en simulación.

## Flujo de interfaz

El formulario existente conservará sus controles y diseño. Al enviar:

1. `AuthController` validará campos no vacíos;
2. la vista activará su estado ocupado;
3. se ejecutará el login asíncrono;
4. una respuesta válida actualizará `AppContext.session` y navegará al dashboard;
5. un error se mostrará mediante el componente de feedback existente;
6. el estado ocupado se desactivará siempre.

El texto que actualmente acepta cualquier credencial se reemplazará por una instrucción neutral. El encabezado privado distinguirá entre:

- `Modo demostración` para una sesión demo;
- `Acceso API · módulos restantes en demostración` para una sesión autenticada por la API.

Al cerrar sesión, `AppShell` limpiará primero los tokens y después eliminará la sesión del contexto y navegará a `/login`.

## Manejo de errores

La UI nunca mostrará códigos HTTP, tracebacks ni contenido técnico completo. El mapeo será:

| Condición | Mensaje para la interfaz |
|---|---|
| Conexión rechazada o API inaccesible | No fue posible conectar con el servicio. |
| Timeout | El servicio tardó demasiado en responder. |
| 401 | Usuario o contraseña incorrectos. |
| 403 | No tienes permiso para realizar esta acción. |
| 404 | No se encontró el recurso solicitado. |
| 422 | Los datos enviados no son válidos. |
| 500–599 | El servicio no está disponible temporalmente. |
| JSON inválido o contrato inesperado | El servicio devolvió una respuesta no válida. |

Los detalles técnicos podrán registrarse con `logging`, limitados al tipo de error, método y ruta. No se registrarán bodies de autenticación, headers de autorización, contraseñas ni tokens.

## Pruebas

Las pruebas usarán `pytest`, `asyncio.run()` y `httpx.MockTransport`; no requieren `pytest-asyncio` ni una API activa.

Se cubrirán:

- carga de `API_BASE_URL` y compatibilidad con `IP_ADDRESS`;
- rechazo de configuración incompleta;
- login exitoso y payload exacto;
- almacenamiento de ambos tokens;
- incorporación posterior del Bearer Token;
- limpieza de tokens al cerrar sesión o fallar el login;
- credenciales incorrectas;
- API no disponible;
- timeout;
- respuestas 403, 404, 422 y 500;
- JSON inválido;
- ausencia o tipo incorrecto de los tokens;
- conservación de los adaptadores demo para los módulos fuera de alcance.

Cada comportamiento nuevo seguirá el ciclo prueba fallida, implementación mínima y prueba satisfactoria.

## Dependencias

Se declararán como dependencias directas:

- `httpx` para comunicación HTTP asíncrona y `MockTransport`;
- `python-dotenv` para cargar `.env` en ejecución local.

Ambas ya aparecen transitivamente en `uv.lock`, pero deben figurar en `pyproject.toml` porque el código del proyecto las importará directamente. No se añadirán otras librerías.

## Archivos previstos

Crear:

- `src/esiqie_dictamenes/core/settings.py`;
- `src/esiqie_dictamenes/features/usuarios/repository.py`;
- `src/esiqie_dictamenes/infrastructure/http/__init__.py`;
- `src/esiqie_dictamenes/infrastructure/http/api_client.py`;
- `src/esiqie_dictamenes/infrastructure/http/auth_repository.py`;
- `src/esiqie_dictamenes/infrastructure/http/token_store.py`;
- `tests/core/test_settings.py`;
- `tests/infrastructure/http/test_api_client.py`;
- `tests/infrastructure/http/test_auth_repository.py`;
- `tests/infrastructure/http/test_token_store.py`.

Modificar:

- `pyproject.toml` y `uv.lock`;
- `src/esiqie_dictamenes/core/errors.py`;
- `src/esiqie_dictamenes/core/services.py`;
- `src/esiqie_dictamenes/core/context.py` si la limpieza de sesión requiere exponer una operación explícita;
- `src/esiqie_dictamenes/app.py`;
- `src/esiqie_dictamenes/features/auth/repository.py`;
- `src/esiqie_dictamenes/features/auth/view.py`;
- `src/esiqie_dictamenes/features/usuarios/controller.py`;
- `src/esiqie_dictamenes/infrastructure/demo/auth_repository.py`;
- `src/esiqie_dictamenes/shared/components/app_shell.py`;
- pruebas existentes afectadas;
- `docs/architecture.md` y `NOTES.md`.

## Criterios de aceptación

- El login real usa la URL y ruta configuradas, sin URLs hardcodeadas en la UI.
- Un login exitoso crea una sesión no demo, guarda los tokens en memoria y navega al área privada.
- El cierre de sesión borra los tokens.
- Los fallos previstos muestran mensajes comprensibles sin códigos HTTP.
- Ninguna prueba depende del backend real.
- Los demás endpoints y el generador PDF permanecen sin cambios funcionales.
- `.env` continúa excluido de Git y no se exponen secretos.

