---
name: Project Docs
description: Usa esta skill cuando haya que documentar un repositorio o proyecto (memoria técnica, arquitectura, estructura de carpetas, guía de uso, informe para presentar) y entregarlo en Markdown, HTML, Word (.docx) o PDF. También para actualizar documentación existente sin inventar datos.
---

# Project Docs

Produce documentación técnica **verificable** a partir del repositorio real: rutas,
comandos, artefactos y cifras que se pueden comprobar. Nunca inventes módulos,
métricas ni pasos que el proyecto no tenga.

## Cuándo usarla

- "documenta este proyecto", "memoria técnica", "explica la estructura"
- preparar una entrega, informe o presentación
- actualizar `README.md`, la arquitectura o la guía de carpetas
- convertir documentación Markdown a `.docx` / `.pdf`

## Flujo de trabajo

1. **Inventario real** (no de memoria):
   - `git ls-files` o un árbol de directorios.
   - Lee `README.md`, `README_CARPETAS.md`, manifiestos (`requirements.txt`,
     `package.json`, `pyproject.toml`).
   - Identifica puntos de entrada y orquestadores.
2. **Extracción estructurada**:
   - arquitectura y componentes; flujo de datos de extremo a extremo;
   - mapa carpeta por carpeta (qué genera cada una y qué la consume);
   - comando(s) para ejecutar y flags documentados;
   - configuración/entorno (`.env.example`, modos, degradación);
   - resultados reales (conteos de artefactos, tablas, métricas) leídos de los
     archivos, no supuestos.
3. **Redacción** en `docs/<proyecto>-memoria.md` siguiendo
   `references/estructura-informe.md`. Español claro, tablas para lo comparable.
4. **Validación** (obligatoria): ninguna sección vacía, ningún `TODO`, ningún
   comando sin probar/comprobar, todas las rutas existen, cifras con su fuente.
5. **Exportación**: `scripts/md_a_docx.py` para Word; para PDF usa la misma
   skill (conversión directa si hay Word/LibreOffice). Si no, imprime el HTML.

## Reglas

- Cita la ruta del archivo que respalda cada afirmación técnica.
- Si algo no se puede verificar, dilo explícitamente ("no verificado").
- No pegues secretos: muestra `.env.example`, nunca `.env`.
- Distingue lo **real** (p. ej. Supabase/Atlas) de lo **simulado/local**
  (SQLite, NDJSON) — es un error frecuente en informes.
- Mantén el documento reproducible: quien lo lea debe poder ejecutar el
  proyecto con los comandos que aparecen.

## Entregables típicos

| Salida | Uso |
|---|---|
| `docs/<proyecto>-memoria.md` | fuente de verdad, versionable en git |
| `docs/<proyecto>-memoria.docx` | entrega formal / imprimir |
| `docs/<proyecto>-memoria.pdf` | entrega formal |
| `docs/presentacion.md` | guion de diapositivas |

## Exportar a Word/PDF

```bash
# Word
python .opencode/skills/project-docs/scripts/md_a_docx.py \
  docs/mi-memoria.md docs/mi-memoria.docx \
  --titulo "Memoria técnica" --subtitulo "Proyecto X" --autor "Tu Nombre"

# Word + PDF (requiere Word instalado o LibreOffice `soffice`)
python .opencode/skills/project-docs/scripts/md_a_docx.py \
  docs/mi-memoria.md docs/mi-memoria.docx --pdf
```

Dependencia del script: `python-docx` (`pip install python-docx`). La conversión
a PDF prueba, en orden: `docx2pdf` (Word), `soffice` (LibreOffice) y, en
Windows, **Word vía COM** con `scripts/docx_a_pdf.ps1`. Ese último paso también
actualiza el índice (TOC) y los campos, así que el PDF sale con números de
página reales. Si ninguno está disponible, exporta el `.docx` y se imprime a
PDF desde Word/navegador.

Comprobación rápida del resultado: el `.docx` debe tener tantas tablas e
imágenes como el Markdown, ninguna línea con `**`, `|` o ```` ``` ```` residual,
y el PDF debe abrir con cabecera `%PDF`.

## Estructura recomendada

Lee `references/estructura-informe.md` para el esqueleto completo (portada,
resumen, arquitectura, estructura, datos, pipeline, resultados, operación,
limitaciones y anexos).
