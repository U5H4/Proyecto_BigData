"""Convierte Markdown a Word (.docx) y, opcionalmente, a PDF.

Uso:
    python md_a_docx.py entrada.md salida.docx --titulo "Memoria" \
        --subtitulo "Proyecto X" --autor "Nombre" [--pdf]

Soporta: encabezados ``#``..``######``, parrafos, listas ``-``/``*``/``1.``,
tablas GFM, bloques de codigo con ``` ```, citas ``>``, imagenes
``![alt](ruta)``, reglas ``---``, negrita ``**x**``, codigo `` `x` `` y
cursiva ``*x*``.

Dependencia: ``python-docx``. Para PDF intenta ``docx2pdf``, luego LibreOffice
(``soffice``) y, en Windows, Word via COM (``docx_a_pdf.ps1``, que ademas
actualiza el indice y los numeros de pagina). Si ninguno existe, deja el .docx
listo para imprimir.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

_INLINE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|\*[^*\n]+\*)")
_TABLA_SEP = re.compile(r"^:?-{3,}:?$")


# --------------------------------------------------------------------------
# Utilidades DOCX
# --------------------------------------------------------------------------
def _fuente_base(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    normal.paragraph_format.space_after = Pt(6)


def _pie_de_pagina(doc: Document) -> None:
    for section in doc.sections:
        p = section.footer.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run()
        fld = OxmlElement("w:fldSimple")
        fld.set(qn("w:instr"), "PAGE")
        run._r.append(fld)


def _indice(doc: Document) -> None:
    doc.add_heading("Indice", level=1)
    p = doc.add_paragraph()
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), r'TOC \o "1-3" \h \z \u')
    p._p.append(fld)
    doc.add_page_break()


def _portada(doc: Document, titulo: str, subtitulo: str, autor: str) -> None:
    for _ in range(6):
        doc.add_paragraph()
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = t.add_run(titulo)
    run.bold = True
    run.font.size = Pt(26)
    run.font.color.rgb = RGBColor(0x26, 0x32, 0x38)
    if subtitulo:
        s = doc.add_paragraph()
        s.alignment = WD_ALIGN_PARAGRAPH.CENTER
        rs = s.add_run(subtitulo)
        rs.font.size = Pt(14)
        rs.font.color.rgb = RGBColor(0x60, 0x7D, 0x8B)
    for _ in range(8):
        doc.add_paragraph()
    if autor:
        a = doc.add_paragraph()
        a.alignment = WD_ALIGN_PARAGRAPH.CENTER
        a.add_run(autor).font.size = Pt(12)
    doc.add_page_break()


def _texto_con_formato(par, texto: str) -> None:
    """Agrega ``texto`` a ``par`` interpretando negrita, codigo y cursiva."""
    for trozo in _INLINE.split(texto):
        if not trozo:
            continue
        if trozo.startswith("**") and trozo.endswith("**") and len(trozo) > 4:
            par.add_run(trozo[2:-2]).bold = True
        elif trozo.startswith("`") and trozo.endswith("`") and len(trozo) > 2:
            run = par.add_run(trozo[1:-1])
            run.font.name = "Consolas"
            run.font.size = Pt(9.5)
        elif trozo.startswith("*") and trozo.endswith("*") and len(trozo) > 2:
            par.add_run(trozo[1:-1]).italic = True
        else:
            par.add_run(trozo)


def _sombra_celda(celda, color: str = "D9E2F3") -> None:
    tc_pr = celda._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), color)
    tc_pr.append(shd)


def _tabla(doc: Document, filas: list[list[str]]) -> None:
    if not filas:
        return
    columnas = max(len(f) for f in filas)
    tabla = doc.add_table(rows=len(filas), cols=columnas)
    try:
        tabla.style = "Light Grid Accent 1"
    except KeyError:
        tabla.style = "Table Grid"
    for i, fila in enumerate(filas):
        for j in range(columnas):
            celda = tabla.cell(i, j)
            celda.text = ""
            par = celda.paragraphs[0]
            valor = fila[j] if j < len(fila) else ""
            _texto_con_formato(par, valor.strip())
            for run in par.runs:
                run.font.size = Pt(9.5)
                if i == 0:
                    run.bold = True
            if i == 0:
                _sombra_celda(celda)
    doc.add_paragraph()


def _codigo(doc: Document, lineas: list[str]) -> None:
    par = doc.add_paragraph()
    par.paragraph_format.left_indent = Inches(0.25)
    par.paragraph_format.space_before = Pt(4)
    par.paragraph_format.space_after = Pt(8)
    for i, linea in enumerate(lineas):
        run = par.add_run(linea)
        run.font.name = "Consolas"
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x37, 0x47, 0x4F)
        if i < len(lineas) - 1:
            run.add_break()


def _imagen(doc: Document, ruta: Path, alt: str, base: Path) -> None:
    candidata = ruta if ruta.is_absolute() else (base / ruta)
    if candidata.exists():
        try:
            doc.add_picture(str(candidata), width=Inches(6.0))
            doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        except Exception:  # noqa: BLE001 - imagen invalida, no romper el documento
            doc.add_paragraph(f"[Imagen no legible: {ruta}]")
    else:
        doc.add_paragraph(f"[Imagen no encontrada: {ruta}]")
    if alt:
        cap = doc.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = cap.add_run(alt)
        run.italic = True
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x60, 0x7D, 0x8B)


# --------------------------------------------------------------------------
# Conversion
# --------------------------------------------------------------------------
def _sin_frontmatter(lineas: list[str]) -> list[str]:
    if lineas and lineas[0].strip() == "---":
        for i in range(1, min(len(lineas), 30)):
            if lineas[i].strip() == "---":
                cuerpo = lineas[1:i]
                if any(":" in l for l in cuerpo):
                    return lineas[i + 1:]
                break
    return lineas


def convertir(md: Path, docx: Path, titulo: str, subtitulo: str, autor: str) -> Path:
    lineas = _sin_frontmatter(md.read_text(encoding="utf-8-sig").splitlines())
    doc = Document()
    _fuente_base(doc)

    _portada(doc, titulo or md.stem, subtitulo, autor)
    _indice(doc)

    i = 0
    dentro_codigo = False
    bloque: list[str] = []
    filas_tabla: list[list[str]] = []

    def cerrar_tabla() -> None:
        nonlocal filas_tabla
        if filas_tabla:
            _tabla(doc, filas_tabla)
            filas_tabla = []

    while i < len(lineas):
        linea = lineas[i]
        limpia = linea.strip()

        if limpia.startswith("```"):
            if not dentro_codigo:
                cerrar_tabla()
                dentro_codigo = True
                bloque = []
            else:
                _codigo(doc, bloque)
                dentro_codigo = False
            i += 1
            continue
        if dentro_codigo:
            bloque.append(linea)
            i += 1
            continue

        if limpia.startswith("|") and limpia.endswith("|"):
            celdas = [c.strip() for c in limpia.strip("|").split("|")]
            if not all(_TABLA_SEP.match(c) for c in celdas if c):
                filas_tabla.append(celdas)
            i += 1
            continue
        cerrar_tabla()

        if not limpia:
            i += 1
            continue

        imagen = re.match(r"!\[(.*?)\]\((.*?)\)", limpia)
        if imagen:
            _imagen(doc, Path(imagen.group(2)), imagen.group(1), md.parent)
            i += 1
            continue

        encabezado = re.match(r"^(#{1,6})\s+(.*)$", limpia)
        if encabezado:
            nivel = len(encabezado.group(1))
            doc.add_heading(encabezado.group(2).strip(), level=nivel)
            i += 1
            continue

        if limpia in ("---", "***", "___"):
            doc.add_paragraph()
            i += 1
            continue

        if limpia.startswith(">"):
            par = doc.add_paragraph()
            par.paragraph_format.left_indent = Inches(0.3)
            _texto_con_formato(par, limpia.lstrip("> ").strip())
            for run in par.runs:
                run.italic = True
            i += 1
            continue

        bullet = re.match(r"^[-*+]\s+(.*)$", limpia)
        if bullet:
            par = doc.add_paragraph(style="List Bullet")
            _texto_con_formato(par, bullet.group(1))
            i += 1
            continue

        numerada = re.match(r"^\d+[.)]\s+(.*)$", limpia)
        if numerada:
            par = doc.add_paragraph(style="List Number")
            _texto_con_formato(par, numerada.group(1))
            i += 1
            continue

        par = doc.add_paragraph()
        _texto_con_formato(par, limpia)
        i += 1

    cerrar_tabla()
    if bloque:
        _codigo(doc, bloque)

    _pie_de_pagina(doc)
    docx.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(docx))
    return docx


def _pdf_con_word(docx: Path) -> bool:
    """DOCX -> PDF con Microsoft Word via COM (Windows), sin docx2pdf."""
    if sys.platform != "win32":
        return False
    script = Path(__file__).with_name("docx_a_pdf.ps1")
    if not script.exists():
        return False
    destino = docx.with_suffix(".pdf")
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(script), "-Docx", str(docx.resolve()),
             "-Pdf", str(destino.resolve())],
            check=True,
            capture_output=True,
        )
        return destino.exists()
    except Exception:  # noqa: BLE001 - Word no disponible o bloqueado
        return False


def a_pdf(docx: Path) -> bool:
    try:
        from docx2pdf import convert  # type: ignore
        convert(str(docx))
        return True
    except Exception:  # noqa: BLE001 - sin docx2pdf/Word
        pass
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        try:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir",
                 str(docx.parent), str(docx)],
                check=True,
            )
            return True
        except Exception:  # noqa: BLE001 - LibreOffice fallo
            pass
    return _pdf_con_word(docx)


def main() -> int:
    ap = argparse.ArgumentParser(description="Markdown -> DOCX/PDF")
    ap.add_argument("entrada", type=Path)
    ap.add_argument("salida", type=Path)
    ap.add_argument("--titulo", default="")
    ap.add_argument("--subtitulo", default="")
    ap.add_argument("--autor", default="")
    ap.add_argument("--pdf", action="store_true")
    args = ap.parse_args()

    if not args.entrada.exists():
        print(f"No existe: {args.entrada}", file=sys.stderr)
        return 2

    docx = convertir(args.entrada, args.salida, args.titulo, args.subtitulo, args.autor)
    print(f"OK -> {docx}")
    if args.pdf:
        if a_pdf(docx):
            print(f"PDF -> {docx.with_suffix('.pdf')}")
        else:
            print("PDF no generado: instala Word/docx2pdf o LibreOffice. "
                  "El .docx esta listo para imprimir a PDF.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
