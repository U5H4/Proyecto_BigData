---
title: Presentacion - Corporativo JUC
subtitle: Guion de diapositivas y defensa
date: 2026-11-05
---

# Presentacion del proyecto

Guion para exponer el pipeline de datos de **Corporativo JUC S.A. de C.V.**
Duracion objetivo: **12–15 minutos** + preguntas. Cada diapositiva indica que
decir, que mostrar en pantalla y que evidencia del repositorio la respalda.

## Antes de empezar (checklist de demo)

- [ ] Abrir `data/reports/reporte.html` en el navegador (funciona offline).
- [ ] Tener a mano una terminal en la raiz del proyecto.
- [ ] Verificar que `.venv` existe y que el pipeline corre:
      `.\.venv\Scripts\python.exe src\run_all.py --listar`.
- [ ] Tener abiertos `data/sql/01_ddl.sql` y `data/nosql/01_pipelines.js`.
- [ ] Opcional: correr `pytest -q` antes de la exposicion para confirmar 161 passed.
- [ ] No mostrar `.env` en pantalla (credenciales). Si hace falta, mostrar
      `.env.example`.

---

# Diapositiva 1 — Portada y problema

**Titulo:** Corporativo JUC — Pipeline de datos de extremo a extremo
**Subtitulo:** ETL + PostgreSQL + MongoDB + Cloud + Visualizacion

**Que decir:**

> Corporativo JUC es una empresa ficticia de electronica en Mexico. El problema
> es que la informacion esta dispersa en tres fuentes distintas y con errores:
> CSV, JSON y hojas de calculo. No se puede saber que se vende, que se ve y que
> se pierde. El proyecto construye un pipeline reproducible que integra todo.

**En pantalla:** nombre, materia, autor, fecha y repositorio.

---

# Diapositiva 2 — Arquitectura y flujo

**Que decir:**

> Cuatro componentes obligatorios. El ETL en Python y Pandas extrae y limpia.
> PostgreSQL guarda lo estructurado con integridad referencial. MongoDB guarda
> lo semiestructurado. Cloud es Supabase y Atlas, con degradacion local para que
> el proyecto se pueda reproducir sin credenciales.

**Diagrama (texto para la diapositiva):**

```
CSV / JSON / XLSX
        |
        v
   ETL (10 reglas)  --> evidencia de calidad
        |
        +--> PostgreSQL (3FN, vista, 20 indices)
        +--> MongoDB (3 colecciones, 12 indices)
                    |
                    v
        Analisis (Pandas) + Integracion SQL/NoSQL
                    |
                    v
        12 visualizaciones Plotly -> reporte.html
```

**Evidencia:** `src/run_all.py` (5 etapas), `README.md` seccion de arquitectura.

---

# Diapositiva 3 — Fuentes y calidad (Parte I)

**Que decir:**

> Se generan tres fuentes con errores deliberados para demostrar la limpieza.
> La fuente A son cinco CSV con duplicados, precios como texto, fechas
> ambiguas y ciudades con varias grafias. La fuente B son tres JSON con
> atributos variables por familia. La fuente C son cuatro hojas de calculo
> exportadas de Google Sheets: sucursales, proveedores, promociones y objetivos.

**Tabla para la diapositiva:**

| Fuente | Archivos | Errores intencionales |
|---|---|---|
| A — CSV | 5 | duplicados, tipos mezclados, nulos, fechas y ciudades sucias |
| B — JSON | 3 | estructura variable, anidamiento, atributos opcionales |
| C — Sheets/XLSX | 4 | categorias y regiones inconsistentes |

**Evidencia:** `data/raw/`, `data/reports/perfil_columnas.csv`.

---

# Diapositiva 4 — ETL: 10 transformaciones (Parte II)

**Que decir:**

> Cada transformacion es auditable: registra filas antes, filas despues,
> registros afectados y la regla aplicada. Eso permite defender el trabajo con
> evidencia y no con afirmaciones. Ademas se validan los minimos del enunciado.

**Mostrar:** `data/reports/calidad_transformaciones.csv` (una fila por regla y
tabla) y `data/reports/validacion_minimos.csv`.

| ID | Regla |
|---|---|
| T01 | duplicados |
| T02 | normalizacion de texto |
| T03 | nulos |
| T04 | tipos |
| T05 | fechas |
| T06 | precios |
| T07 | cantidades |
| T08 | categorias y ciudades |
| T09 | columnas redundantes |
| T10 | campos derivados |

**Frase clave:** "los datos no se limpian a ojo: cada cambio deja evidencia".

---

# Diapositiva 5 — PostgreSQL (Parte III)

**Que decir:**

> El modelo esta en tercera forma normal: seis tablas operativas, dos
> dimensiones y una tabla de hechos. Hay claves primarias, foraneas, unicidad y
> restricciones CHECK, por ejemplo que el total sea subtotal menos descuento.
> Sobre las columnas de filtro y orden se crean 20 indices.

**Mostrar:** el diagrama ER (`data/reports/modelo_relacional.png`) y un fragmento
de `data/sql/01_ddl.sql`.

**Resultado de indices:** `data/sql/03_explain_analyze.md` compara el plan antes
y despues: de recorrido completo a `SEARCH ... USING INDEX`, con mejora de
**4.03x** (0.874 ms sin indice frente a 0.217 ms con el indice).

**Frase clave:** "el indice no es decorativo: se demuestra con EXPLAIN ANALYZE".

---

# Diapositiva 6 — MongoDB (Parte IV)

**Que decir:**

> MongoDB se usa donde el esquema no es fijo. El catalogo tiene un subdocumento
> de atributos distinto por familia; las resenas anidan al cliente; la
> navegacion es una coleccion de eventos. Hay 15 consultas con find y
> countDocuments y 12 pipelines de agregacion con match, group, unwind y lookup.

**Mostrar:** `data/nosql/indices.json`, `data/nosql/01_pipelines.js`.

**Ejemplo estrella (A08):**

```javascript
db.productos.find(
  { "atributos.procesador": { $exists: true } },
  { nombre: 1, "atributos.procesador": 1, _id: 0 }
)
```

> En SQL esto obligaria a alterar el esquema; en MongoDB es una consulta
> dinamica sobre un atributo que solo existe en una familia.

---

# Diapositiva 7 — Integracion SQL + NoSQL (Parte V)

**Que decir:**

> La pregunta central es si los productos mas vistos son los mas vendidos. No se
> puede responder con un solo motor: las ventas estan en PostgreSQL y las
> visitas en MongoDB. Se extraen ambos lados y se cruzan con merge de Pandas.

**Resultado:**

- Pearson **+0.323** entre visitas y unidades vendidas (productos vistos y
  vendidos); al ampliar la poblacion baja a **+0.146** (todos) y **+0.104**
  (solo visitados).
- Spearman **+0.270** sobre todos los productos.
- **63** productos con trafico y cero ventas, de los **92** que nunca se
  vendieron (catalogo de 606).

> Conclusion: la navegacion ayuda, pero no garantiza la venta. Hay dinero
> invertido en trafico que no convierte.

**Mostrar:** `data/reports/analisis/11_correlacion_visitas_ventas.csv`.

---

# Diapositiva 8 — Hallazgos de negocio

**Que decir:** (elegir 4, no leer todos)

| Hallazgo | Dato |
|---|---|
| Facturacion | $127,336,206.51 (solo pedidos completados) |
| Pedidos | 1,483 completados de 2,259 |
| Ticket promedio | $85,863.93 |
| Cancelacion | 34.35% |
| Utilidad bruta | $37,982,053.12 |
| Margen real | 29.46% |
| Pareto | 124 de 514 productos (24.1%) explican el 80% de la venta |
| Categoria mas rentable | Computadoras ($19,450,980.64) |

**Evidencia:** `data/reports/analisis/01_kpis_generales.csv`.

---

# Diapositiva 9 — Cloud (Parte VI)

**Que decir:**

> Cloud Database es real: PostgreSQL 17 en Supabase por session pooler IPv4 y
> MongoDB Atlas 8.0 en un cluster M0. Cloud Storage y Cloud Computing estan
> simulados: el layout de carpetas reproduce el almacenamiento y el codigo es
> portable a una VM o contenedor.

**Ser honesto:** no se aprovisionan buckets ni VMs; se documenta el layout y la
portabilidad. Sin credenciales el pipeline degrada a SQLite y NDJSON sin fallar.

**Mostrar:** `.env.example` (nunca `.env`) y `data/reports/integracion_entorno.md`.

---

# Diapositiva 10 — Visualizacion (Parte VII)

**Que decir:**

> Doce visualizaciones interactivas con Plotly: hover con el valor exacto, zoom
> y series aislables. Todas se reunen en un solo reporte HTML que funciona
> offline porque el JavaScript de Plotly viaja con el proyecto.

**Demo:** abrir `data/reports/reporte.html` y mostrar:
1. Serie temporal (zoom).
2. Pareto (concentracion).
3. Dispersion visitas vs ventas (correlacion).
4. Embudo navegacion-compra.

**Si no hay internet:** el reporte funciona igual; `plotly.min.js` es local.

---

# Diapositiva 11 — Reproducibilidad y pruebas

**Que decir:**

> Todo el proyecto se regenera con una orden. La semilla 20260904 fija los
> datos, asi que los resultados son reproducibles. Hay 161 pruebas automaticas
> que cubren transformacion, integracion, analisis y orquestacion.

```powershell
.\.venv\Scripts\python.exe src\run_all.py --con-tests
```

**Resultado esperado:** 5 etapas OK + 161 pruebas en verde.

**Frase clave:** "no es una entrega de archivos sueltos: es un pipeline que se
puede volver a ejecutar y da lo mismo".

---

# Diapositiva 12 — Conclusiones y mejoras

**Que decir:**

> El proyecto cumple el flujo completo: fuentes sucias, ETL auditable, dos
> motores con modelos adecuados a cada tipo de dato, integracion entre ambos,
> cloud y visualizacion. Lo que mejoraria es la operacion: orquestacion
> programada, monitoreo de calidad y pruebas de carga. El siguiente paso natural
> seria un modelo predictivo de churn o de recomendacion.

**Cierre:** "gracias, el repositorio y el reporte estan disponibles para
revisar cualquier cifra".

---

# Preguntas probables del jurado

**¿Por que PostgreSQL y MongoDB?**
Porque el dato transaccional es relacional y necesita integridad; el catalogo,
las resenas y la navegacion tienen esquema variable. Usar un solo motor obliga a
torcer el modelo.

**¿Como garantizan que el ETL no inventa datos?**
Cada regla deja filas antes/despues y afectados en
`calidad_transformaciones.csv`; los minimos se validan en
`validacion_minimos.csv`; hay 161 pruebas.

**¿Los indices realmente sirven?**
Si: `03_explain_analyze.md` muestra el plan antes y despues, con el cambio a
`SEARCH ... USING INDEX` y el tiempo de cada version.

**¿Que pasa si no hay credenciales cloud?**
El pipeline degrada a SQLite y NDJSON. Los artefactos `data/sql` y `data/nosql`
se generan igual. Nada falla.

**¿Los datos son reales?**
No, son sinteticos y reproducibles con semilla. Las conclusiones describen a la
empresa ficticia; la metodologia es la que se evalua.

**¿Que no cubre el proyecto?**
Streaming en tiempo real, alta disponibilidad, buckets/VMs reales y modelos
predictivos. Esta declarado en limitaciones.

---

# Anexo — Cifras de referencia rapida

| Dato | Valor |
|---|---|
| Semilla | 20260904 |
| Clientes | 1,862 (1,314 con pedido) |
| Productos | 606 (514 vendidos) |
| Pedidos | 3,277 (2,259 unicos) |
| Detalle de pedido | 3,891 |
| Resenas | 2,475 |
| Eventos de navegacion | 4,236 |
| Consultas SQL | 20 |
| Pipelines MongoDB | 12 |
| Consultas find/count | 15 |
| Indices SQL / MongoDB | 20 / 12 |
| Visualizaciones | 12 |
| Pruebas | 161 |
