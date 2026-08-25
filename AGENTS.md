# ESIQIE-DICTAMENES

Frontend para visualización de datos alumnos.
La interfáz debe ser capáz de:

- Generación de dictamenes con archivo `PDF`.
- Buscar dictamenes por numero de boleta de estudiante o por año.
- Crear usuarios.
- Eliminar dictamenes
- Login.
- Modificacion de dictamenes.
- Buscar inscritos.
La carpeta /@assets tiene las imagenes necesarias para el frontend.

## Stack

- **Interfáz gráfica**: Flet.
- **Consumo asíncrono de la API.**: HTTPX.
- **Manejo de .env.**: python-dotenv.
- **estión de dependencias y entorno virtual** : uv.
- **Generación de PDFs**: FPDF y datetime.
- **Manejo de Rutas del sistema**: os.

## Setup

```bash
uv init
uv venv
uv run flet run --web --port 8501               # Inicia la interfáz de usuario
```

## Estilo

- Uso de excepciones en casos errores; La interfáz no debe mostrar un código de error.
- Async/await en todo I/O.

## Arquitectura

- La documentación actual de la API se encuentra en [127.0.0.1](http://127.0.0.1/docs).Puedes usar el servidor MCP de chrome-devtools para visualizarla.
- Tienes referencias de las rutas a las que debes acceder en el @.env.example
- Tienes referencias de como deben verse los archivos en @referencias/*
- Tienes un frontend de referencia en:
  [GESTION_ESCOLAR_FRONTEND](https://github.com/The-C6H6/GESTION_ESCOLAR_FRONTEND).

## Tests

- pytest.
- Mockea las llamadas HTTP en tests unitarios.
- No dependas del backend real para ejecutar tests unitarios.

## Límites

- NUNCA hagas commit de `.env`. Está en `.gitignore`.
- Si vas a añadir una dependencia, pregunta primero.

## Scope

Este repositorio contiene únicamente el frontend.

- No modificar el backend.
- No modificar la base de datos directamente.
- Toda comunicación con datos debe realizarse mediante la API.
