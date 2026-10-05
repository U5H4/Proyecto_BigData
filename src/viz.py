"""Graficos del reporte de analisis (matplotlib, salida PNG estatica).

Decisiones deliberadas:

- **Estatica, no interactiva.** Un PNG se pega en la documentacion, se
  versiona en git y se lee sin instalar nada. La alternativa (plotly/HTML)
  aniade una dependencia y un archivo que nadie puede revisar en un diff.
- **Backend Agg.** matplotlib no abre ventana: en un servidor o en CI
  `plt.show()` no existiria. Se elige explicitamente el backend antes de
  importar pyplot.
- **Una sola fuente de verdad.** Cada grafico se arma con los DataFrames que
  devuelve `analysis.construir_todos()`, nunca recalculando. Un grafico no
  puede contradecir al CSV que esta a su lado.
- **Sin estado global entre graficos.** Cada funcion crea y cierra su figura.
  matplotlib avisaria "more than 20 figures" si se filtraran.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (el backend debe fijarse antes)
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

import analysis  # noqa: E402
from config import COLOR_ALERTA, COLOR_CATEGORIA, COLOR_NEUTRO, COLOR_OK, FIGURES, REPORTS  # noqa: E402
from utils import LOG, asegurar_dir, numero, subtitulo, tabla, titulo  # noqa: E402

ANCHO, ALTO = 11, 6
DPI = 140
PALETA = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3", "#937860", "#7A7A7A"]


# --------------------------------------------------------------------------
# Utilidades de dibujo
# --------------------------------------------------------------------------
def _miles(x, _pos) -> str:
    """1234567 -> '1.2M'. Los importes son grandes y sin abreviar los ejes
    quedan ilegibles."""
    v = float(x)
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:,.1f}M".replace(",", " ")
    if abs(v) >= 1_000:
        return f"{v / 1_000:,.0f}k".replace(",", " ")
    return f"{v:,.0f}".replace(",", " ")


def _cortar(texto: str, largo: int = 34) -> str:
    texto = str(texto)
    return texto if len(texto) <= largo else texto[: largo - 1] + "\u2026"


def _nuevo(titulo: str, subtitulo: str = "", figsize=(ANCHO, ALTO)):
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color("#B0BEC5")
    ax.tick_params(colors="#455A64", labelsize=9)
    ax.set_title(titulo, fontsize=14, fontweight="bold", color="#263238", loc="left", pad=18)
    if subtitulo:
        ax.text(0, 1.02, subtitulo, transform=ax.transAxes, fontsize=9.5,
                color="#607D8B", va="bottom")
    return fig, ax


def _pie(ax, texto: str) -> None:
    """Nota al pie. Se parte en varias lineas: en una sola, `bbox_inches`
    estira el lienzo hasta hacer un PNG panoramico con el grafico encogido."""
    import textwrap
    ax.text(0, -0.16, "\n".join(textwrap.wrap(texto, width=115)),
            transform=ax.transAxes, fontsize=8.5, color="#78909C", va="top")


def _guardar(fig, nombre: str, destino: Path) -> Path:
    ruta = destino / f"{nombre}.png"
    fig.savefig(ruta, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return ruta


def _barras_h(ax, etiquetas, valores, color, fmt="{:,.0f}"):
    y = np.arange(len(etiquetas))
    ax.barh(y, valores, color=color, height=0.68)
    ax.set_yticks(y)
    ax.set_yticklabels(etiquetas, fontsize=9)
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(FuncFormatter(_miles))
    ax.grid(axis="x", color="#ECEFF1", linewidth=0.8)
    ax.set_axisbelow(True)
    limite = max(valores) if len(valores) else 1
    for yi, v in zip(y, valores):
        ax.text(v + limite * 0.015, yi, fmt.format(v), va="center",
                fontsize=8.5, color="#455A64")


def _vacio(ax, mensaje: str) -> None:
    ax.text(0.5, 0.5, mensaje, transform=ax.transAxes, ha="center",
            va="center", fontsize=12, color="#B0BEC5")
    ax.set_xticks([])
    ax.set_yticks([])


# --------------------------------------------------------------------------
# 1. Serie temporal
# --------------------------------------------------------------------------
def grafico_ventas_mensuales(d: pd.DataFrame) -> plt.Figure:
    fig, ax = _nuevo(
        "Facturacion mensual",
        "Barras: pesos facturados. Linea: ticket promedio por pedido.",
    )
    if d.empty:
        _vacio(ax, "sin ventas mensuales")
        return fig
    x = np.arange(len(d))
    parcial = d["mes_incompleto"].fillna(False).to_numpy()
    colores = [PALETA[0] if not p else "#B0BEC5" for p in parcial]
    ax.bar(x, d["facturacion"], color=colores, width=0.72)
    ax.set_xticks(x)
    ax.set_xticklabels(d["anio_mes"], rotation=60, ha="right", fontsize=8)
    ax.yaxis.set_major_formatter(FuncFormatter(_miles))
    ax.grid(axis="y", color="#ECEFF1", linewidth=0.8)
    ax.set_axisbelow(True)

    ax2 = ax.twinx()
    ax2.plot(x, d["ticket_promedio"], color=COLOR_ALERTA, marker="o", markersize=4,
             linewidth=2, zorder=5)
    ax2.set_ylabel("Ticket promedio", fontsize=9.5, color=COLOR_ALERTA)
    ax2.tick_params(axis="y", colors=COLOR_ALERTA, labelsize=9)
    ax2.yaxis.set_major_formatter(FuncFormatter(_miles))
    ax2.spines["top"].set_visible(False)

    if parcial.any():
        ax.annotate("ultimo mes\npuede estar incompleto",
                    xy=(x[-1], d["facturacion"].iloc[-1]),
                    xytext=(x[-1] - 4, d["facturacion"].iloc[-1] * 1.05),
                    fontsize=8, color="#78909C",
                    arrowprops=dict(arrowstyle="->", color="#B0BEC5"))
    _pie(ax, f"Total {numero(d['facturacion'].sum())} | "
             f"{numero(d['pedidos'].sum())} pedidos | "
             f"{numero(d['unidades'].sum())} unidades")
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# 2. Mix por categoria
# --------------------------------------------------------------------------
def grafico_mix_categoria(d: pd.DataFrame) -> plt.Figure:
    fig, ax = _nuevo(
        "Mix de facturacion por categoria",
        "Participacion de cada familia sobre la venta total.",
    )
    if d.empty:
        _vacio(ax, "sin datos por categoria")
        return fig
    d = d.sort_values("facturacion", ascending=True)
    colores = [COLOR_CATEGORIA.get(c, COLOR_NEUTRO) for c in d["segmento"]]
    _barras_h(ax, [_cortar(s) for s in d["segmento"]], d["facturacion"].to_numpy(), colores)
    ax.set_xlabel("Facturacion", fontsize=9.5, color="#455A64")
    for yi, (_, fila) in zip(np.arange(len(d)), d.iterrows()):
        ax.text(0, yi, f"  {fila.participacion_pct:.1f}%", va="center",
                fontsize=8.5, color="white", fontweight="bold")
    _pie(ax, " | ".join(
        f"{_cortar(r.segmento, 18)}: {r.margen_pct:.1f}% margen"
        for r in d.sort_values("facturacion", ascending=False).itertuples()
    ))
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# 3. Ticket por canal
# --------------------------------------------------------------------------
def grafico_ticket_canal(d: pd.DataFrame) -> plt.Figure:
    fig, ax = _nuevo(
        "Facturacion y margen por canal de venta",
        "Barras: facturacion. Puntos: margen real del canal.",
    )
    if d.empty:
        _vacio(ax, "sin datos por canal")
        return fig
    d = d.sort_values("facturacion", ascending=False).reset_index(drop=True)
    x = np.arange(len(d))
    ax.bar(x, d["facturacion"], color=[PALETA[i % len(PALETA)] for i in range(len(d))],
           width=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels([_cortar(s, 18) for s in d["segmento"]], fontsize=9.5)
    ax.yaxis.set_major_formatter(FuncFormatter(_miles))
    ax.grid(axis="y", color="#ECEFF1", linewidth=0.8)
    ax.set_axisbelow(True)

    ax2 = ax.twinx()
    ax2.plot(x, d["margen_pct"], color=COLOR_ALERTA, marker="D", markersize=7,
             linewidth=0, zorder=5)
    for xi, v in zip(x, d["margen_pct"]):
        if pd.notna(v):
            ax2.annotate(f"{v:.1f}%", (xi, v), textcoords="offset points",
                         xytext=(0, 11), ha="center", fontsize=9,
                         color=COLOR_ALERTA, fontweight="bold")
    ax2.set_ylabel("Margen real %", fontsize=9.5, color=COLOR_ALERTA)
    ax2.tick_params(axis="y", colors=COLOR_ALERTA, labelsize=9)
    ax2.spines["top"].set_visible(False)
    _pie(ax, " | ".join(
        f"{_cortar(r.segmento, 16)}: ticket {numero(r.ticket_promedio)}"
        for r in d.itertuples()
    ))
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# 4. Ley de Pareto
# --------------------------------------------------------------------------
def grafico_pareto(d: pd.DataFrame) -> plt.Figure:
    fig, ax = _nuevo(
        "Ley de Pareto: concentracion de la venta",
        "Barras: facturacion por producto (top 60). Linea: % acumulado del total.",
    )
    if d.empty:
        _vacio(ax, "sin productos vendidos")
        return fig
    top = d.head(60).reset_index(drop=True)
    x = np.arange(len(top))
    ax.bar(x, top["facturacion"], color=PALETA[0], width=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels([_cortar(p, 16) for p in top["producto_nombre"]],
                       rotation=90, fontsize=6.5)
    ax.yaxis.set_major_formatter(FuncFormatter(_miles))
    ax.set_xlabel("Producto (60 mas facturados)", fontsize=9.5, color="#455A64")
    ax.grid(axis="y", color="#ECEFF1", linewidth=0.8)
    ax.set_axisbelow(True)

    ax2 = ax.twinx()
    ax2.plot(x, top["acumulado_pct"], color=COLOR_ALERTA, linewidth=2.2)
    ax2.axhline(80, color=COLOR_OK, linestyle="--", linewidth=1.4)
    ax2.text(0, 81.5, "80% de la venta", fontsize=9, color=COLOR_OK, fontweight="bold")
    ax2.set_ylim(0, 105)
    ax2.set_ylabel("% acumulado", fontsize=9.5, color=COLOR_ALERTA)
    ax2.tick_params(axis="y", colors=COLOR_ALERTA, labelsize=9)
    ax2.spines["top"].set_visible(False)

    n80 = int(d["productos_hasta_80"].iloc[0])
    p80 = float(d["pct_productos_hasta_80"].iloc[0])
    _pie(ax, f"{n80} de {len(d)} productos ({p80:.1f}% del catalogo vendido) "
             f"explican el 80% de la facturacion")
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# 5. Segmentacion de clientes
# --------------------------------------------------------------------------
def grafico_segmentos(d: pd.DataFrame) -> plt.Figure:
    fig, ax = _nuevo(
        "Segmentacion de clientes (RFM)",
        "Barras: numero de clientes. Linea: participacion en la facturacion.",
    )
    if d.empty:
        _vacio(ax, "sin segmentos")
        return fig
    d = d.reset_index(drop=True)
    x = np.arange(len(d))
    tono = {
        "Campeones": "#2E7D32", "Leales": "#66BB6A", "Potenciales": "#9CCC65",
        "Nuevos": "#42A5F5", "En riesgo": "#FFA726", "Dormidos": "#B0BEC5",
    }
    ax.bar(x, d["clientes"], color=[tono.get(s, COLOR_NEUTRO) for s in d["segmento"]],
           width=0.62)
    ax.set_xticks(x)
    ax.set_xticklabels(d["segmento"], fontsize=9.5)
    ax.grid(axis="y", color="#ECEFF1", linewidth=0.8)
    ax.set_axisbelow(True)
    for xi, (n, _) in zip(x, zip(d["clientes"], d["clientes"])):
        ax.text(xi, n + d["clientes"].max() * 0.02, f"{n:,}", ha="center",
                fontsize=9, color="#455A64")

    ax2 = ax.twinx()
    ax2.plot(x, d["participacion_pct"], color=COLOR_ALERTA, marker="o",
             markersize=6, linewidth=2, zorder=5)
    for xi, v in zip(x, d["participacion_pct"]):
        ax2.annotate(f"{v:.1f}%", (xi, v), textcoords="offset points",
                     xytext=(0, -16), ha="center", fontsize=8.5, color=COLOR_ALERTA)
    ax2.set_ylabel("% de la facturacion", fontsize=9.5, color=COLOR_ALERTA)
    ax2.tick_params(axis="y", colors=COLOR_ALERTA, labelsize=9)
    ax2.spines["top"].set_visible(False)
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# 6. Embudo
# --------------------------------------------------------------------------
def grafico_embudo(d: pd.DataFrame) -> plt.Figure:
    fig, ax = _nuevo(
        "Embudo de navegacion a compra",
        "Todos los pasos en la misma unidad: numero de eventos.",
        figsize=(ANCHO, 5.4),
    )
    if d.empty:
        _vacio(ax, "sin eventos de navegacion")
        return fig
    colores = [PALETA[0], PALETA[1], COLOR_OK]
    y = np.arange(len(d))[::-1]
    ax.barh(y, d["eventos"], color=colores[: len(d)], height=0.6)
    ax.set_yticks(y)
    ax.set_yticklabels(d["paso"], fontsize=10)
    ax.xaxis.set_major_formatter(FuncFormatter(_miles))
    ax.grid(axis="x", color="#ECEFF1", linewidth=0.8)
    ax.set_axisbelow(True)
    for yi, fila in zip(y, d.itertuples()):
        ax.text(fila.eventos * 1.02, yi,
                f"{fila.eventos:,}  ({fila.participacion_pct:.0f}% del inicio)",
                va="center", fontsize=9.5, color="#37474F")
    ax.set_xlim(0, d["eventos"].max() * 1.45)
    caidas = d["caida_vs_paso_anterior_pct"].dropna()
    if len(caidas):
        _pie(ax, " | ".join(f"caida al paso siguiente: {v:.0f}%" for v in caidas))
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# 7. Correlacion visitas / ventas
# --------------------------------------------------------------------------
def grafico_correlacion(detalle: pd.DataFrame, metricas: pd.DataFrame) -> plt.Figure:
    fig, ax = _nuevo(
        "La navegacion predice la venta?",
        "Cada punto es un producto. Eje x: visualizaciones. Eje y: unidades vendidas.",
    )
    if detalle.empty:
        _vacio(ax, "sin datos de navegacion")
        return fig
    v = detalle["visitas"].astype(float)
    u = detalle["unidades"].astype(float)
    sizes = 18 + 150 * (u / u.max() if u.max() else 1)
    colores = np.where(u > 0, PALETA[0], COLOR_ALERTA)
    ax.scatter(v, u, s=sizes, c=colores, alpha=0.45, edgecolors="none")

    sub = detalle[(v > 0) & (u > 0)]
    if len(sub) > 2:
        pendiente, intercepto = np.polyfit(sub["visitas"], sub["unidades"], 1)
        xs = np.linspace(0, v.max(), 50)
        ax.plot(xs, intercepto + pendiente * xs, color=COLOR_ALERTA, linewidth=2,
                linestyle="--", zorder=6)
        ax.text(0.97, 0.94,
                f"ajuste lineal (solo visitados y vendidos)\npendiente = {pendiente:.2f} unidades/visita",
                transform=ax.transAxes, ha="right", va="top", fontsize=9,
                color=COLOR_ALERTA,
                bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                          edgecolor="#FFCDD2"))

    ax.set_xlabel("Visualizaciones del producto", fontsize=9.5, color="#455A64")
    ax.set_ylabel("Unidades vendidas", fontsize=9.5, color="#455A64")
    ax.xaxis.set_major_formatter(FuncFormatter(_miles))
    ax.yaxis.set_major_formatter(FuncFormatter(_miles))
    ax.grid(color="#ECEFF1", linewidth=0.8)
    ax.set_axisbelow(True)

    cero = int((detalle["unidades"] == 0).sum())
    lineas = [
        f"{_cortar(r.metrica, 38)}: {r.valor:.3f}" for r in metricas.itertuples()
        if r.metrica.startswith(("Pearson", "Spearman"))
    ]
    _pie(ax, " | ".join(lineas)
         + f" | {cero} productos con visitas y cero venta (rojo)")
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# 8-9. Inventario muerto y under-exposure
# --------------------------------------------------------------------------
def grafico_inventario_muerto(d: pd.DataFrame) -> plt.Figure:
    fig, ax = _nuevo(
        "Inversion que no convierte: visitas sin ninguna venta",
        "Productos que reciben trafico y no registran una sola unidad vendida.",
        figsize=(ANCHO, 6.4),
    )
    if d.empty:
        _vacio(ax, "todo el trafico navega productos que despues venden")
        return fig
    total_muertos = int((d["unidades"] == 0).sum())
    d = d.head(15).reset_index(drop=True)
    _barras_h(ax, [_cortar(f"{r.nombre} ({_cortar(r.categoria, 12)})", 40) for r in d.itertuples()],
              d["visitas"].to_numpy(), COLOR_ALERTA)
    ax.set_xlabel("Visualizaciones", fontsize=9.5, color="#455A64")
    _pie(ax, f"Mostrados los {len(d)} con mas trafico, de {total_muertos} productos "
             f"que reciben visitas y no registran ninguna unidad vendida")
    fig.tight_layout()
    return fig


def grafico_under_exposure(d: pd.DataFrame) -> plt.Figure:
    fig, ax = _nuevo(
        "Under-exposure: se vende mucho con pocas visitas",
        "Top 15 por unidades vendidas, con su trafico real.",
        figsize=(ANCHO, 6.4),
    )
    if d.empty:
        _vacio(ax, "sin ventas para comparar")
        return fig
    d = d.head(15).reset_index(drop=True)
    _barras_h(ax, [_cortar(f"{r.nombre} ({_cortar(r.categoria, 12)})", 40) for r in d.itertuples()],
              d["unidades"].to_numpy(), COLOR_OK)
    ax.set_xlabel("Unidades vendidas", fontsize=9.5, color="#455A64")
    _pie(ax, "visitas por unidad en el top 5: " + " | ".join(
        f"{_cortar(r.nombre, 20)} = {r.visitas_por_unidad:.2f}"
        for r in d.head(5).itertuples()
    ))
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# 10. Descuentos
# --------------------------------------------------------------------------
def grafico_descuentos(d: pd.DataFrame) -> plt.Figure:
    fig, ax = _nuevo(
        "Los descuentos se pagan con margen",
        "Barras: margen real por rango de descuento. Puntos: lineas vendidas.",
    )
    if d.empty:
        _vacio(ax, "sin ventas con descuento")
        return fig
    d = d.reset_index(drop=True)
    x = np.arange(len(d))
    ax.bar(x, d["margen_pct"].astype(float),
           color=[COLOR_ALERTA if (pd.notna(v) and v < 25) else PALETA[0]
                  for v in d["margen_pct"]], width=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels(d["rango_descuento"].astype(str), fontsize=10)
    ax.set_ylabel("Margen real %", fontsize=9.5, color="#455A64")
    ax.grid(axis="y", color="#ECEFF1", linewidth=0.8)
    ax.set_axisbelow(True)
    for xi, v in zip(x, d["margen_pct"]):
        if pd.notna(v):
            ax.text(xi, v + 0.4, f"{v:.1f}%", ha="center", fontsize=9, color="#455A64")

    ax2 = ax.twinx()
    ax2.plot(x, d["unidades"], color=COLOR_NEUTRO, marker="s", markersize=7, linewidth=0)
    ax2.set_ylabel("Unidades", fontsize=9.5, color=COLOR_NEUTRO)
    ax2.tick_params(axis="y", colors=COLOR_NEUTRO, labelsize=9)
    ax2.yaxis.set_major_formatter(FuncFormatter(_miles))
    ax2.spines["top"].set_visible(False)
    _pie(ax, " | ".join(
        f"{r.rango_descuento}: -{r.descuento_pct_del_ingreso:.1f}% del ingreso"
        for r in d.itertuples() if pd.notna(r.descuento_pct_del_ingreso)
    ))
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# 11. Satisfaccion
# --------------------------------------------------------------------------
def grafico_satisfaccion(d: pd.DataFrame) -> plt.Figure:
    fig, ax = _nuevo(
        "Distribucion de calificaciones",
        "Numero de resenas por estrellas y tasa de positiva.",
    )
    if d.empty:
        _vacio(ax, "sin resenas")
        return fig
    d = d.reset_index(drop=True)
    x = np.arange(len(d))
    colores = [COLOR_OK if c >= 4 else (COLOR_ALERTA if c <= 2 else PALETA[1])
               for c in d["calificacion"]]
    ax.bar(x, d["resenas"], color=colores, width=0.6)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{c:.0f} estrellas" for c in d["calificacion"]], fontsize=10)
    ax.set_ylabel("Resenas", fontsize=9.5, color="#455A64")
    ax.grid(axis="y", color="#ECEFF1", linewidth=0.8)
    ax.set_axisbelow(True)
    for xi, fila in zip(x, d.itertuples()):
        ax.text(xi, fila.resenas + d["resenas"].max() * 0.02,
                f"{fila.resenas:,}\n{fila.tasa_positiva_pct:.0f}% pos.",
                ha="center", fontsize=8.5, color="#455A64")
    ax.set_ylim(0, d["resenas"].max() * 1.22)
    _pie(ax, f"total {numero(d['resenas'].sum())} resenas | "
             f"{numero(d['verificadas'].sum())} verificadas")
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# 12. Sucursales
# --------------------------------------------------------------------------
def grafico_sucursales(d: pd.DataFrame) -> plt.Figure:
    fig, ax = _nuevo(
        "Facturacion por sucursal",
        "Cada barra es una sucursal fisica; el color es su region.",
    )
    if d.empty:
        _vacio(ax, "sin ventas por sucursal")
        return fig
    d = d.sort_values("facturacion", ascending=True)
    tono_region = {"Sureste": "#55A868", "Centro": "#4C72B0",
                   "Occidente": "#DD8452", "Norte": "#8172B3", "Nacional": COLOR_NEUTRO}
    colores = [tono_region.get(r, COLOR_NEUTRO) for r in d["region"]]
    etiquetas = [f"{_cortar(n, 22)} - {_cortar(c, 14)}" for n, c in zip(d["nombre"], d["ciudad"])] \
        if "nombre" in d.columns else [str(i) for i in d["id_sucursal"]]
    _barras_h(ax, etiquetas, d["facturacion"].to_numpy(), colores)
    ax.set_xlabel("Facturacion", fontsize=9.5, color="#455A64")
    for yi, v in zip(np.arange(len(d)), d["ticket_promedio"]):
        ax.text(0, yi, f"  ticket {numero(v)}", va="center", fontsize=8,
                color="white", fontweight="bold")
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# Orquestacion
# --------------------------------------------------------------------------
GRAFICOS = [
    ("01_ventas_mensuales", "Serie temporal de ventas", lambda r: grafico_ventas_mensuales(r["02_ventas_mensuales"])),
    ("02_mix_categoria", "Mix por categoria", lambda r: grafico_mix_categoria(r["03_mix_categoria"])),
    ("03_ticket_por_canal", "Ticket y margen por canal", lambda r: grafico_ticket_canal(r["04_mix_canal"])),
    ("04_ley_de_pareto", "Ley de Pareto", lambda r: grafico_pareto(r["15_ley_pareto"])),
    ("05_segmentos_clientes", "Segmentacion RFM", lambda r: grafico_segmentos(r["07_segmentos_clientes"])),
    ("06_embudo_navegacion", "Embudo navegacion-compra", lambda r: grafico_embudo(r["09_embudo_navegacion"])),
    ("07_correlacion_visitas_ventas", "Correlacion navegacion-venta",
     lambda r: grafico_correlacion(r["12_dispersion_visitas_ventas"], r["11_correlacion_visitas_ventas"])),
    ("08_inventario_muerto", "Visitas sin venta", lambda r: grafico_inventario_muerto(r["13_inventario_muerto"])),
    ("09_under_exposure", "Under-exposure", lambda r: grafico_under_exposure(r["14_under_exposure"])),
    ("10_impacto_descuentos", "Descuentos vs margen", lambda r: grafico_descuentos(r["17_impacto_descuentos"])),
    ("11_satisfaccion", "Calificaciones", lambda r: grafico_satisfaccion(r["18_satisfaccion"])),
    ("12_por_sucursal", "Facturacion por sucursal", lambda r: grafico_sucursales(r["06_por_sucursal"])),
]


def construir_todos(resultados: dict[str, pd.DataFrame], destino: Path | None = None) -> pd.DataFrame:
    destino = asegurar_dir(destino or FIGURES)
    indice = []
    for nombre, titulo, fn in GRAFICOS:
        try:
            fig = fn(resultados)
            ruta = _guardar(fig, nombre, destino)
            kb = ruta.stat().st_size / 1024
            indice.append({"grafico": nombre, "titulo": titulo, "archivo": ruta.name,
                           "estado": "OK", "kb": round(kb, 1), "error": ""})
        except Exception as exc:  # noqa: BLE001 - un grafico roto no debe tumbar el pipeline
            indice.append({"grafico": nombre, "titulo": titulo, "archivo": "",
                           "estado": "ERROR", "kb": 0.0, "error": f"{type(exc).__name__}: {exc}"})
    return pd.DataFrame(indice)


def main() -> None:
    print(titulo("GRAFICOS DEL REPORTE"))
    asegurar_dir(FIGURES)
    # Mismo motivo que en analysis: una figura renombrada dejaba su PNG viejo.
    for viejo in FIGURES.glob("*.png"):
        viejo.unlink()

    fact = analysis.cargar_fact()
    documentos = analysis.cargar_documentos()
    sucursales = analysis.cargar_sucursales()
    resultados = analysis.construir_todos(fact, documentos, sucursales)
    # Los CSV del analisis se regeneran aqui para que `python src/viz.py` solo
    # produzca figuras y sus numeros no dependan de un paso anterior.
    analysis.guardar(resultados)
    LOG.info("  Analisis recalculado: %d dataframes", len(resultados))

    indice = construir_todos(resultados)
    print(tabla(indice[["grafico", "titulo", "estado", "kb"]]))

    destino = REPORTS / "figuras_indice.csv"
    indice.to_csv(destino, index=False, encoding="utf-8-sig")
    LOG.info("  %d graficos -> %s", len(indice), FIGURES)
    LOG.info("  Indice -> %s", destino)

    fallidos = indice[indice.estado != "OK"]
    if len(fallidos):
        for f in fallidos.itertuples():
            LOG.error("  %s: %s", f.archivo or f.grafico, f.error)
        raise AssertionError(f"{len(fallidos)} graficos fallaron")
    LOG.info("  Todos los graficos generados sin error")


if __name__ == "__main__":
    main()
