# Guía: Probar con Supabase y MongoDB Atlas

Esta guía explica cómo conectar el proyecto a **Supabase (PostgreSQL)** y **MongoDB Atlas (NoSQL)** usando sus propias cuentas.

## 1. ¿Cuándo se conecta a la nube?

El pipeline intenta conectar automáticamente **solo si encuentra credenciales válidas**. 

- Si **NO** hay `.env` con credenciales, o fallan, se usa **SQLite + NDJSON local** (sin subir nada).
- Si **SÍ** hay credenciales correctas, entonces se conecta a Supabase y/o Atlas para crear tablas/colecciones, cargar datos, ejecutar consultas y generar los reportes.

**Importante:** Nunca sube datos a otras cuentas. Usa **únicamente** las credenciales que ustedes definan en `.env`.

## 2. Configurar `.env`

Copien `.env.example` a `.env` y editen solo las variables necesarias.

### Opción A: Supabase con Pooler (Recomendado - IPv4)

El pooler evita problemas de IPv6 en muchas redes.

```env
# PostgreSQL en Supabase
SUPABASE_HOST=aws-0-us-west-2.pooler.supabase.com
SUPABASE_PORT=5432
SUPABASE_DATABASE=postgres
SUPABASE_USER=postgres.<SU_PROYECTO_ID>
SUPABASE_PASSWORD=<SU_PASSWORD_DB>
PG_SSLMODE=require
```

### Opción B: Supabase con conexión directa

```env
PG_HOST=db.<SU_PROYECTO_ID>.supabase.co
PG_PORT=5432
PG_DATABASE=postgres
PG_USER=postgres
PG_PASSWORD=<SU_PASSWORD_DB>
PG_SSLMODE=require
```

Si definen `SUPABASE_HOST`, este tiene prioridad sobre `PG_HOST`.

### MongoDB Atlas

```env
# MongoDB Atlas
MONGO_URI=mongodb+srv://<USUARIO>:<PASSWORD>@<CLUSTER>.mongodb.net/?appName=<CLUSTER_NAME>
MONGO_DB=novacommerce
# Opcional si prefieren usar MONGO_ATLAS_URI explícito
MONGO_ATLAS_URI=mongodb+srv://<USUARIO>:<PASSWORD>@<CLUSTER>.mongodb.net/?appName=<CLUSTER_NAME>
```

## 3. Variables para forzar modo local

Si por algún motivo quieren **evitar** conectar a nube aunque tengan credenciales:

```env
SIN_POSTGRES=1  # Usa SQLite en lugar de PostgreSQL/Supabase
SIN_MONGO=1     # Usa NDJSON local en lugar de MongoDB Atlas
FORZAR_SQLITE=1 # Fuerza a no intentar PostgreSQL
```

## 4. Pasos para probar con sus propias cuentas

1. Crear proyecto en [Supabase](https://supabase.com/) (gratis)
2. Obtener credenciales: `Project Settings > Database > Connection string` (recomendado usar **Session Pooler**)
3. Crear cluster en [MongoDB Atlas](https://www.mongodb.com/atlas) (M0 gratis)
4. Crear usuario DB y permitir acceso desde IPs (o `0.0.0.0/0` para pruebas)
5. Copiar `.env.example` a `.env` y llenar con sus credenciales
6. Ejecutar: `.\.venv\Scripts\python.exe src\run_all.py`
7. Verificar en consola: debería aparecer `Supabase conectado...` y/o `MongoDB conectado...`

## 5. Comprobar que NO sube a cuentas ajenas

- Si `.env` está vacío o con credenciales incorrectas → usa modo **local** (SQLite + NDJSON). No hay conexión.
- Los archivos `data/processed/integracion/novacommerce.db` y `data/processed/integracion/mongo/*.ndjson` se generan **localmente**.
- Los reportes `data/reports/` se generan **localmente**.

## 6. Notas importantes

- **No commitear `.env`**. Ya está en `.gitignore` para evitar subir contraseñas.
- `.env.example` **sí se sube** y sirve de plantilla.
- Con credenciales reales, se crearán tablas (`clientes`, `productos`, `pedidos`, `detalle_pedido`, `pagos`, `categorias`, `dim_ciudades`, `dim_sucursales`, `fact_ventas`, `v_resumen_ventas`) e índices en Supabase.
- En Atlas se crearán las colecciones `productos`, `resenas`, `actividad_usuario` con sus índices.
- Ejecutar `pytest` sigue funcionando igual: los tests usan SQLite temporal (no requieren nube).

**Recomendado:** Primero probar **sin `.env`** (modo local) para verificar que todo funciona. Después añadir sus credenciales y probar conexión real.
