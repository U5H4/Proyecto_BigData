# Esqueleto de memoria técnica (reutilizable)

Adapta los títulos al dominio; no dejes secciones vacías: si algo no aplica,
escribe "No aplica" y por qué.

## Portada

- Título del proyecto
- Subtítulo (materia / entrega)
- Autor(es), institución, fecha, versión
- Enlace al repositorio

## 1. Resumen ejecutivo

- Qué problema resuelve, para quién.
- 3–5 resultados clave con cifras reales.
- Qué se puede ejecutar y con qué comando.

## 2. Objetivo y alcance

- Objetivo general y específicos.
- Dentro / fuera de alcance (explícito).

## 3. Arquitectura

- Diagrama de componentes (texto o imagen).
- Rol de cada componente y por qué se eligió.
- Flujo de datos de extremo a extremo (fuente → ETL → almacenes → análisis →
  visualización).

## 4. Estructura del repositorio

- Árbol comentado carpeta por carpeta.
- Qué genera cada carpeta y quién la consume.
- Archivos de entrada, configuración y secretos (`.env.example`, no `.env`).

## 5. Fuentes de datos

- Origen, formato, tamaño, periodicidad.
- Calidad: errores intencionales y cómo se tratan.
- Esquema por fuente.

## 6. ETL / procesamiento

- Etapas y orden.
- Transformaciones (tabla: id, regla, filas afectadas, evidencia).
- Campos derivados y reglas de negocio.
- Validaciones y mínimos.

## 7. Modelo de datos

- Modelo relacional: tablas, claves, normalización (3FN), vista e índices.
- Modelo documental: colecciones, forma de los documentos, índices.
- Diagrama ER.

## 8. Análisis y resultados

- Preguntas de negocio y su respuesta.
- Tablas de resultados con su fuente (archivo/consulta).
- Visualizaciones (qué muestra cada una y qué conclusión da).

## 9. Operación

- Requisitos e instalación.
- Comandos y flags.
- Modos (nube/local, degradación).
- Pruebas y cómo interpretarlas.

## 10. Limitaciones y trabajo futuro

- Supuestos, riesgos, lo que no cubre.
- Siguientes pasos concretos.

## Anexos

- A. Diccionario de datos
- B. Consultas (SQL / Mongo) y planes
- C. Evidencia de calidad
- D. Índice de figuras y artefactos
- E. Glosario

## Checklist antes de exportar

- [ ] Cada cifra tiene archivo de origen.
- [ ] Todos los comandos existen y están probados.
- [ ] Rutas reales (sin placeholders).
- [ ] Diagramas y figuras referenciadas existen.
- [ ] Sin secretos ni datos personales.
- [ ] Índice/portada con fecha y versión.
- [ ] Ortografía y consistencia de nombres.
