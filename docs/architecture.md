# Arquitectura de ESIQIE-DICTÁMENES

## Objetivo del esqueleto

La aplicación es un frontend Flet web con navegación declarativa, sesión en memoria y datos demostrativos. No consulta el backend ni genera un PDF binario todavía. Los adaptadores reales podrán reemplazar a los adaptadores demo sin cambiar las vistas.

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
Demo infrastructure adapters
```

- `core/` compone rutas, sesión, tema y servicios compartidos.
- `features/` agrupa modelos, contratos, controladores y vistas por caso de uso.
- `infrastructure/demo/` implementa contratos con datos en memoria.
- `shared/components/` contiene controles visuales reutilizables, sin reglas de negocio.
- Las vistas dependen de controladores, nunca de adaptadores concretos.

## Navegación y sesión

`ft.Router` declara `/login` como ruta pública. El resto de las rutas se renderiza dentro de un layout privado con navegación lateral y encabezado común. Si no existe una sesión en memoria, el layout redirige a `/login`. Cerrar sesión borra ese estado y vuelve al acceso.

La sesión es deliberadamente efímera. El adaptador demo acepta cualquier usuario y contraseña no vacíos y marca la sesión como “Modo demostración”.

## Contratos para la API

- `AuthRepository`: autenticación y registro de `username`, `password` e `is_admin`.
- `DictamenRepository`: búsqueda por boleta o año, consulta por clave, creación, modificación de `dictaminacion` y eliminación por claves.
- `AlumnoRepository`: consulta de inscritos y búsqueda de materias reprobadas.
- `PdfGenerator`: recibe `PdfRequest` y devuelve `GeneratedDocument`.

Las variables requeridas por los futuros adaptadores HTTP están documentadas en `.env.example`. El esqueleto no carga `.env` ni realiza llamadas de red.

## Datos de API y datos de PDF

`DictamenCreate` contiene únicamente los campos previstos para la API. El nombre del director y las materias elegibles pertenecen a `PdfRequest`, por lo que no contaminan el payload de creación. Al modificar, la interfaz solo construye `DictamenUpdate(dictaminacion=...)`; clave, boleta y año permanecen de solo lectura.

El generador demo devuelve un nombre de archivo y `is_simulation=True`, pero ningún contenido binario. Esto evita ofrecer una descarga que aparente ser un PDF válido.

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

La composición ocurre en `core/services.py`. Para conectar la API se añadirán implementaciones HTTP asíncronas de los repositorios y se inyectarán desde una nueva fábrica. La generación real seguirá el mismo patrón con una implementación de `PdfGenerator` basada en las referencias de `referencias/`.
