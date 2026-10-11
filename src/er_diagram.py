"""Diagrama Entidad-Relacion (modelo relacional en 3FN) y su explicacion.

Genera, ambos en data/reports/:
  - modelo_relacional.png   (diagrama con matplotlib)
  - modelo_relacional.md    (por que el modelo esta en 3FN)

Se guarda en reports/ y no en figures/ porque la etapa de graficos limpia los
*.png de figures/; el diagrama del modelo debe sobrevivir a esa corrida.
Se ejecuta desde integration.main() para que el diagrama siempre acompanhe a
la corrida: si cambia el esquema, cambia el diagrama.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from config import REPORTS
from etl_load import ESQUEMA_DIM_SUCURSALES, ESQUEMA_SQL, ORDEN_CARGA
from utils import LOG, asegurar_dir, subtitulo

# Posicion (esquina inferior izquierda) y tamano de cada entidad en el lienzo.
LAYOUT = {
    "dim_ciudades": (0.4, 2.3, 2.5),
    "clientes": (3.6, 2.0, 2.6),
    "pedidos": (6.9, 2.0, 2.6),
    "categorias": (0.4, 5.6, 2.5),
    "productos": (3.6, 5.4, 2.6),
    "detalle_pedido": (6.9, 4.6, 2.7),
    "dim_sucursales": (10.3, 2.0, 2.4),
    "pagos": (10.3, 4.6, 2.4),
}

# Cardinalidades para rotular cada relacion (padre 1 -> hijo N).
ETIQUETAS = {
    ("dim_ciudades", "clientes"): ("1", "N"),
    ("categorias", "productos"): ("1", "N"),
    ("clientes", "pedidos"): ("1", "N"),
    ("dim_sucursales", "pedidos"): ("1", "N"),
    ("productos", "detalle_pedido"): ("1", "N"),
    ("pedidos", "detalle_pedido"): ("1", "N"),
    ("pedidos", "pagos"): ("1", "N"),
}


def _columnas(tabla: str) -> dict[str, str]:
    return ESQUEMA_DIM_SUCURSALES if tabla == "dim_sucursales" else ESQUEMA_SQL[tabla]


def _dibujar(reports_dir: Path) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

    from integration import CLAVES_FORANEAS, CLAVES_PRIMARIAS

    asegurar_dir(reports_dir)
    fig, ax = plt.subplots(figsize=(13.5, 9))
    ax.set_xlim(0, 13.2)
    ax.set_ylim(1.2, 9.6)
    ax.axis("off")
    ax.set_title("NovaCommerce - Modelo relacional normalizado (3FN)",
                 fontsize=14, fontweight="bold")

    centros: dict[str, tuple[float, float]] = {}
    cajas: dict[str, tuple[float, float, float, float]] = {}
    colores = {
        "dim_ciudades": "#dbeafe", "categorias": "#dbeafe",
        "dim_sucursales": "#dbeafe", "clientes": "#dcfce7",
        "productos": "#fef9c3", "pedidos": "#ffe4e6",
        "detalle_pedido": "#ede9fe", "pagos": "#ffedd5",
    }

    for tabla in ORDEN_CARGA:
        x, y, w = LAYOUT[tabla]
        cols = _columnas(tabla)
        pk = CLAVES_PRIMARIAS.get(tabla)
        fks = {c for h, c, _, _ in CLAVES_FORANEAS if h == tabla}
        h = 0.42 + 0.2 * len(cols)
        ax.add_patch(FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.03,rounding_size=0.06",
            linewidth=1.3, edgecolor="#334155", facecolor=colores[tabla]))
        ax.text(x + w / 2, y + h - 0.2, tabla, ha="center", va="center",
                fontsize=10.5, fontweight="bold", color="#0f172a")
        ax.plot([x, x + w], [y + h - 0.34, y + h - 0.34], color="#94a3b8", lw=0.8)
        for i, col in enumerate(cols):
            marca = "PK" if col == pk else ("FK" if col in fks else "")
            color = "#b45309" if marca == "PK" else ("#1d4ed8" if marca == "FK" else "#334155")
            ax.text(x + 0.1, y + h - 0.55 - 0.2 * i,
                    f"{marca:>2} {col}", ha="left", va="center",
                    fontsize=6.8, family="monospace", color=color)
        centros[tabla] = (x + w / 2, y + h / 2)
        cajas[tabla] = (x, y, w, h)

    def borde(tabla: str, hacia: tuple[float, float]) -> tuple[float, float]:
        x, y, w, h = cajas[tabla]
        cx, cy = x + w / 2, y + h / 2
        dx, dy = hacia[0] - cx, hacia[1] - cy
        if abs(dx) * h > abs(dy) * w:  # sale por izquierda/derecha
            return (x + w, cy) if dx > 0 else (x, cy)
        return (cx, y + h) if dy > 0 else (cx, y)

    for hija, _col, padre, _col_padre in CLAVES_FORANEAS:
        if padre not in LAYOUT or hija not in LAYOUT:
            continue
        p1 = borde(hija, centros[padre])
        p2 = borde(padre, centros[hija])
        ax.add_patch(FancyArrowPatch(
            p1, p2, arrowstyle="-", connectionstyle="arc3,rad=0.12",
            color="#64748b", lw=1.1, shrinkA=2, shrinkB=2))
        l1, l2 = ETIQUETAS.get((padre, hija), ("1", "N"))
        ax.text(p1[0] * 0.55 + p2[0] * 0.45, p1[1] * 0.55 + p2[1] * 0.45 - 0.12,
                l2, fontsize=8, color="#475569", fontweight="bold")
        ax.text(p2[0] * 0.55 + p1[0] * 0.45, p2[1] * 0.55 + p1[1] * 0.45 - 0.12,
                l1, fontsize=8, color="#475569", fontweight="bold")

    ax.text(6.6, 1.45,
            "Ademas: fact_ventas (tabla analitica desnormalizada) declara FK hacia "
            "pedidos, productos, clientes, categorias, dim_sucursales y dim_ciudades; "
            "v_resumen_ventas es una vista con JOIN de 5 tablas.",
            ha="center", fontsize=8.5, style="italic", color="#334155")
    ax.text(0.4, 9.4, "PK = llave primaria   FK = llave foranea   "
                      "1:N = uno a muchos", fontsize=8.5, color="#334155")

    destino = reports_dir / "modelo_relacional.png"
    fig.tight_layout()
    fig.savefig(destino, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return destino


def _texto_3fn() -> str:
    from integration import CLAVES_FORANEAS, CLAVES_FORANEAS_FACT, CLAVES_PRIMARIAS

    fks = "\n".join(
        f"| `{h}.{c}` | `{p}.{cp}` |" for h, c, p, cp in CLAVES_FORANEAS
    )
    fks_fact = "\n".join(
        f"| `fact_ventas.{c}` | `{p}.{cp}` |" for c, p, cp in CLAVES_FORANEAS_FACT
    )
    pks = "\n".join(f"| `{t}` | `{k}` |" for t, k in CLAVES_PRIMARIAS.items())
    return f"""# Modelo relacional y normalizacion (3FN)

Generado: {datetime.now():%Y-%m-%d %H:%M:%S}

![Diagrama ER](modelo_relacional.png)

## Tablas y llaves primarias

| Tabla | Llave primaria |
|---|---|
{pks}

## Llaves foraneas

| Columna hija | Referencia |
|---|---|
{fks}

## Llaves foraneas de la tabla analitica

`fact_ventas` es el desnormalizado intencional, pero conserva la llave de cada
dimension y las declara como FK, de modo que el modelo estrella queda completo
tambien en el motor (y visible en el *schema visualizer*):

| Columna `fact_ventas` | Referencia |
|---|---|
{fks_fact}

## Por que el modelo esta en Tercera Forma Normal

El dataset del ETL llega **desnormalizado** (una fila por linea de venta con
ciudad, categoria, cliente y producto repetidos). `etl_load.py` lo parte en
dimensiones y hechos para cumplir 1FN, 2FN y 3FN:

1. **1FN (atomicidad).** Ninguna celda guarda listas. Los atributos del
   producto (`atributos`, `etiquetas`) y la actividad web, que si son listas o
   subdocumentos, se sacan del modelo relacional y viven en MongoDB, donde el
   documento anidado es la unidad natural.

2. **2FN (sin dependencias parciales).** En `detalle_pedido` la llave es
   `id_detalle` (linea). Los datos que dependen solo de `id_producto`
   (`nombre`, `categoria`, `precio`, `margen_bruto`) se movieron a `productos`;
   los que dependen solo de `id_pedido` (`fecha_pedido`, `canal_venta`,
   `id_sucursal`) se movieron a `pedidos`. Una linea ya no repite el nombre del
   producto ni la fecha del pedido.

3. **3FN (sin dependencias transitivas).** Ninguna columna no clave depende de
   otra columna no clave:
   - `productos.categoria` era un atributo de la categoria; se extrajo a
     `categorias.nombre` y queda la FK `productos.id_categoria`.
   - `clientes.ciudad/region` dependian de la ciudad; se extrajo a
     `dim_ciudades` y queda la FK `clientes.id_ciudad` (la ciudad, no el
     cliente, define la region).
   - `pedidos.id_sucursal` apunta a `dim_sucursales`, que concentra direccion,
     region y metros cuadrados de la tienda.

## Relaciones (cardinalidad 1:N)

- `dim_ciudades` 1:N `clientes`
- `categorias` 1:N `productos`
- `clientes` 1:N `pedidos`
- `dim_sucursales` 1:N `pedidos`
- `pedidos` 1:N `detalle_pedido`
- `productos` 1:N `detalle_pedido`
- `pedidos` 1:N `pagos`

## Objetos de servicio (no normalizados, a proposito)

- `fact_ventas`: tabla ancha derivada del dataset limpio. No es una vista SQL
  porque es el **contrato de columnas** que consumen los reportes: materializar
  el JOIN una vez evita repetirlo en cada grafico. Aun asi declara FK hacia
  `pedidos`, `productos`, `clientes`, `categorias`, `dim_sucursales` y
  `dim_ciudades` para que el esquema estrella sea explicito.
- `v_resumen_ventas`: **vista** que encapsula el JOIN de 5 tablas
  (`pedidos`, `detalle_pedido`, `clientes`, `productos`, `categorias`) para el
  pulso mensual. Aqui la vista si aplica porque el resultado se consulta a
  menudo y su definicion se gobierna en la base, no en el ETL.
"""


def generar_modelo(reports_dir: Path | None = None) -> Path:
    """Genera el PNG del diagrama ER y el documento de 3FN."""
    reports_dir = reports_dir or REPORTS
    LOG.info(subtitulo("Diagrama ER y justificacion 3FN"))
    png = _dibujar(reports_dir)
    LOG.info("  Diagrama ER -> %s", png)
    md = reports_dir / "modelo_relacional.md"
    md.write_text(_texto_3fn(), encoding="utf-8")
    LOG.info("  Modelo relacional (3FN) -> %s", md)
    return png


if __name__ == "__main__":
    generar_modelo()
