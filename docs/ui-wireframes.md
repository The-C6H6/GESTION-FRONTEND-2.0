# Wireframes aprobados

## 1. Layout privado

```text
┌──────────────────────┬─────────────────────────────────────────────────────┐
│ ESIQIE-DICTÁMENES    │ Sistema de Gestión   Modo demostración   usuario   │
├──────────────────────┼─────────────────────────────────────────────────────┤
│ Inicio               │                                                     │
│ Buscar dictámenes    │                                                     │
│ Dictaminar           │                ÁREA DE CONTENIDO                    │
│ Eliminar dictámenes  │                                                     │
│ Buscar inscrito      │                                                     │
│ Crear usuario        │                                                     │
│                      │                                                     │
│ [ Cerrar sesión ]    │                                                     │
└──────────────────────┴─────────────────────────────────────────────────────┘
```

## 2. Búsqueda de dictámenes

```text
┌─ Búsqueda de dictámenes ───────────────────────────────────────────────────┐
│ Buscar por [ Boleta ▼ ] [ valor........................ ] [ Buscar ]       │
├──────────┬────────────┬────────────────────┬──────┬────────────────┬────────┤
│ Clave    │ Boleta     │ Alumno             │ Año  │ Dictaminación  │ Acción │
├──────────┼────────────┼────────────────────┼──────┼────────────────┼────────┤
│ D-00081  │ 2020123456 │ Ana López Martínez │ 2025 │ ...            │ Editar │
│ D-00132  │ 2020123456 │ Ana López Martínez │ 2026 │ ...            │ Editar │
└──────────┴────────────┴────────────────────┴──────┴────────────────┴────────┘
```

La búsqueda alterna entre boleta y año. Cada dictamen conserva su propia fila y `Clave`, aunque una boleta tenga varios registros.

## 3. Crear usuario

```text
┌─ Crear usuario ─────────────────────────────────────────────────────────────┐
│ Usuario                 [...............................................]   │
│ Contraseña              [...............................................]   │
│ Confirmar contraseña    [...............................................]   │
│ Acceso                   [ Usuario estándar / Administrador ▼ ]            │
│                                                     [ Registrar usuario ]  │
└────────────────────────────────────────────────────────────────────────────┘
```

## 4. Dictaminar y generar PDF

```text
┌─ Nuevo dictamen ────────────────────────────────────────────────────────────┐
│ Origen [ Alumno inscrito / Alumno reprobado ▼ ]                            │
│ [ Boleta o nombre.................... ] [ Periodo actual 20271 ] [Buscar]  │
├─────────────────────────────────────────────────────────────────────────────┤
│ Ana López Martínez · Boleta 2020123456 · Ingeniería Química Industrial     │
│ Materias incluidas automáticamente:                                        │
│   Cálculo          periodo 20252   diferencia 19                           │
│   Termodinámica    periodo 20243   diferencia 28                           │
├─────────────────────────────────────────────────────────────────────────────┤
│ Nombre del director [...................................................]   │
│ Fecha de sesión     [ 11 DE DICIEMBRE ] [ Elegir fecha ]                  │
│ Dictaminación       [ textfield multilínea.............................]   │
│                                      [ Dictaminar y generar PDF ]          │
└─────────────────────────────────────────────────────────────────────────────┘
```

Para “Alumno inscrito” se busca por boleta. Para “Alumno reprobado” se admite boleta o nombre y se muestra el periodo actual editable. La fecha de sesión solo puede cambiarse mediante el calendario y se conserva como un objeto `date`. Solo entran al PDF las materias cuya diferencia esté entre 19 y 28, ambas incluidas; el usuario no puede desmarcarlas.

## 5. Eliminar dictámenes

```text
┌─ Eliminar dictámenes ───────────────────────────────────────────────────────┐
│ [ Eliminar seleccionados ]                                                 │
├─────┬──────────┬────────────┬──────────────────────────┬──────┤             │
│ Sel │ Clave    │ Boleta     │ Alumno                   │ Año  │             │
├─────┼──────────┼────────────┼──────────────────────────┼──────┤             │
│ [x] │ D-00081  │ 2020123456 │ Ana López Martínez       │ 2025 │             │
│ [ ] │ D-00132  │ 2020123456 │ Ana López Martínez       │ 2026 │             │
└─────┴──────────┴────────────┴──────────────────────────┴──────┘             │
└─────────────────────────────────────────────────────────────────────────────┘
```

La operación envía exactamente la lista de claves marcadas.

## 6. Modificar dictamen

```text
┌─ Modificar dictamen ────────────────────────────────────────────────────────┐
│ Boleta: 2020123456        Año: 2026        Clave: D-00132                  │
│                                                                             │
│ Dictaminación [ textfield multilínea................................... ]  │
│                              [ Guardar y generar PDF automáticamente ]      │
└─────────────────────────────────────────────────────────────────────────────┘
```

Boleta, año y clave son informativos y de solo lectura. Guardar modifica únicamente `Dictaminacion` y solicita el nuevo PDF.

## 7. Buscar inscrito

```text
┌─ Buscar inscrito ───────────────────────────────────────────────────────────┐
│ Boleta [....................................................] [ Buscar ]    │
├─────────────────────────────────────────────────────────────────────────────┤
│ Nombre: Ana López Martínez          Carrera: Ing. Química Industrial       │
│ Edad: 22        Género: F           Promedio: 8.4                          │
│ Créditos inscritos: 28              Periodo en que reprobó: 20252          │
│ Reprobadas: Cálculo, Termodinámica                                        │
└─────────────────────────────────────────────────────────────────────────────┘
```
