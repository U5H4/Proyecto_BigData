"""Graficos del reporte de analisis (plotly, salida HTML interactiva).

Decisiones deliberadas:

- **HTML interactivo, no PNG.** Cada grafico se exporta a HTML con plotly, de
  modo que el lector puede hacer *hover* para ver el valor exacto, hacer zoom y
  ocultar series. La libreria `plotly.min.js` se escribe una sola vez en
  `data/figures/` (modo `directory`) y las 12 paginas la reutilizan, asi que no
  se repite 12 veces. Ademas se arma un `data/reports/reporte.html` con las 13
  figuras en una sola pagina (JS incrustado).
- **Una sola fuente de verdad.** Cada grafico se arma con los DataFrames que
  devuelve `analysis.construir_todos()`, nunca recalculando. Un grafico no
  puede contradecir al CSV que esta a su lado.
- **Sin estado global entre graficos.** Cada funcion crea su propia figura y no
  reutiliza nada de la anterior.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import analysis
from config import COLOR_ALERTA, COLOR_CATEGORIA, COLOR_NEUTRO, COLOR_OK, EMPRESA, FIGURES, REPORTS
from utils import LOG, asegurar_dir, numero, tabla, titulo

ALTO = 560
PALETA = ["#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3", "#937860", "#7A7A7A"]
_FUENTE = "Segoe UI, Arial, sans-serif"


# --------------------------------------------------------------------------
# Utilidades de dibujo
# --------------------------------------------------------------------------
def _cortar(texto: str, largo: int = 34) -> str:
    texto = str(texto)
    return texto if len(texto) <= largo else texto[: largo - 1] + "\u2026"


def _fig(titulo_gr: str, subtitulo: str = "", alto: int = ALTO) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        template="plotly_white",
        height=alto,
        margin=dict(l=70, r=70, t=95, b=70),
        font=dict(family=_FUENTE, size=12, color="#37474F"),
        showlegend=False,
        hovermode="closest",
        title=dict(text=f"<b>{titulo_gr}</b>", x=0, xanchor="left",
                   font=dict(size=18, color="#263238")),
    )
    if subtitulo:
        fig.add_annotation(text=subtitulo, xref="paper", yref="paper", x=0, y=1.02,
                           xanchor="left", yanchor="bottom", showarrow=False,
                           font=dict(size=11.5, color="#607D8B"))
    return fig


def _pie(fig: go.Figure, texto: str) -> None:
    """Nota al pie, partida en varias lineas para no ensanchar la figura."""
    import textwrap
    fig.add_annotation(text="<br>".join(textwrap.wrap(texto, width=120)),
                       xref="paper", yref="paper", x=0, y=-0.16,
                       xanchor="left", yanchor="top", showarrow=False, align="left",
                       font=dict(size=10, color="#78909C"))
    fig.update_layout(margin=dict(b=120))


def _vacio(fig: go.Figure, mensaje: str) -> go.Figure:
    fig.add_annotation(text=mensaje, xref="paper", yref="paper", x=0.5, y=0.5,
                       showarrow=False, font=dict(size=14, color="#B0BEC5"))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def _eje_s(ventas: bool = True) -> str:
    """Formato SI: 1234567 -> '1.2M'. Los importes son grandes y sin abreviar
    los ejes quedan ilegibles."""
    return "~s"


# --------------------------------------------------------------------------
# 1. Serie temporal
# --------------------------------------------------------------------------
def grafico_ventas_mensuales(d: pd.DataFrame) -> go.Figure:
    fig = _fig(
        "Facturacion mensual",
        "Barras: pesos facturados. Linea: ticket promedio por pedido.",
    )
    if d.empty:
        return _vacio(fig, "sin ventas mensuales")
    parcial = d["mes_incompleto"].fillna(False).to_numpy()
    colores = ["#B0BEC5" if p else PALETA[0] for p in parcial]
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.09,
                        row_heights=[0.62, 0.38],
                        subplot_titles=("Facturacion", "Ticket promedio por pedido"))
    fig.update_layout(
        template="plotly_white", height=660, margin=dict(l=70, r=40, t=115, b=60),
        font=dict(family=_FUENTE, size=12, color="#37474F"), showlegend=False,
        hovermode="closest",
        title=dict(text="<b>Facturacion mensual</b>", x=0, xanchor="left",
                   font=dict(size=18, color="#263238")),
    )
    fig.add_annotation(text="Barras: pesos facturados. Linea: ticket promedio por pedido.",
                       xref="paper", yref="paper", x=0, y=1.03, xanchor="left",
                       yanchor="bottom", showarrow=False,
                       font=dict(size=11.5, color="#607D8B"))
    fig.add_bar(
        x=d["anio_mes"], y=d["facturacion"], marker_color=colores, name="Facturacion",
        hovertemplate="%{x}<br>Facturacion: %{y:,.0f}<extra></extra>", row=1, col=1,
    )
    fig.add_scatter(
        x=d["anio_mes"], y=d["ticket_promedio"], mode="lines+markers", name="Ticket promedio",
        line=dict(color=COLOR_ALERTA, width=2),
        marker=dict(size=5, color=COLOR_ALERTA),
        hovertemplate="%{x}<br>Ticket promedio: %{y:,.0f}<extra></extra>", row=2, col=1,
    )
    fig.update_xaxes(tickangle=-60, tickfont=dict(size=10))
    fig.update_yaxes(tickformat=_eje_s(), gridcolor="#ECEFF1", row=1, col=1,
                      title_text="Facturacion")
    fig.update_yaxes(tickformat=_eje_s(), gridcolor="#ECEFF1", row=2, col=1,
                      title_text="Ticket promedio")
    nota = " | la barra gris es el ultimo mes (puede estar incompleto)" if parcial.any() else ""
    _pie(fig, f"Total {numero(d['facturacion'].sum())} | "
              f"{numero(d['pedidos'].sum())} pedidos | "
              f"{numero(d['unidades'].sum())} unidades" + nota)
    return fig


# --------------------------------------------------------------------------
# 2. Mix por categoria
# --------------------------------------------------------------------------
def grafico_mix_categoria(d: pd.DataFrame) -> go.Figure:
    fig = _fig(
        "Mix de facturacion por categoria",
        "Participacion de cada familia sobre la venta total.",
    )
    if d.empty:
        return _vacio(fig, "sin datos por categoria")
    d = d.sort_values("facturacion", ascending=True)
    fig.add_bar(
        orientation="h", x=d["facturacion"], y=[_cortar(s) for s in d["segmento"]],
        marker_color=[COLOR_CATEGORIA.get(c, COLOR_NEUTRO) for c in d["segmento"]],
        text=[f"{v:.1f}%" for v in d["participacion_pct"]], textposition="outside",
        hovertemplate="%{y}<br>Facturacion: %{x:,.0f}<extra></extra>",
    )
    fig.update_layout(
        xaxis=dict(title_text="Facturacion", tickformat=_eje_s(), gridcolor="#ECEFF1"),
        yaxis=dict(tickfont=dict(size=11)),
    )
    _pie(fig, " | ".join(
        f"{_cortar(r.segmento, 18)}: {r.margen_pct:.1f}% margen"
        for r in d.sort_values("facturacion", ascending=False).itertuples()
    ))
    return fig


# --------------------------------------------------------------------------
# 3. Ticket por canal
# --------------------------------------------------------------------------
def grafico_ticket_canal(d: pd.DataFrame) -> go.Figure:
    fig = _fig(
        "Facturacion y margen por canal de venta",
        "Barras: facturacion. Texto dentro de la barra: margen real del canal.",
    )
    if d.empty:
        return _vacio(fig, "sin datos por canal")
    d = d.sort_values("facturacion", ascending=False).reset_index(drop=True)
    fig.add_bar(
        x=[_cortar(s, 18) for s in d["segmento"]], y=d["facturacion"],
        marker_color=[PALETA[i % len(PALETA)] for i in range(len(d))],
        text=[f"margen {v:.1f}%" if pd.notna(v) else "" for v in d["margen_pct"]],
        textposition="inside", textfont=dict(color="#FFFFFF", size=12),
        hovertemplate="%{x}<br>Facturacion: %{y:,.0f}<extra></extra>",
    )
    fig.update_layout(
        yaxis=dict(title_text="Facturacion", tickformat=_eje_s(), gridcolor="#ECEFF1"),
    )
    _pie(fig, " | ".join(
        f"{_cortar(r.segmento, 16)}: ticket {numero(r.ticket_promedio)}"
        for r in d.itertuples()
    ))
    return fig


# --------------------------------------------------------------------------
# 4. Ley de Pareto
# --------------------------------------------------------------------------
def grafico_pareto(d: pd.DataFrame) -> go.Figure:
    fig = _fig(
        "Ley de Pareto: concentracion de la venta",
        "Barras: facturacion por producto (top 60). Linea: % acumulado del total.",
    )
    if d.empty:
        return _vacio(fig, "sin productos vendidos")
    top = d.head(60).reset_index(drop=True)
    nombres = top["producto_nombre"].astype(str)
    cortos = [f"{i + 1}) {_cortar(p, 12)}" for i, p in enumerate(nombres)]
    salto = max(1, len(top) // 12)  # 12 etiquetas como maximo: legibles sin hover
    pos = list(range(0, len(top), salto))
    fig.add_bar(
        x=cortos, y=top["facturacion"],
        marker_color=PALETA[0], customdata=nombres,
        hovertemplate="%{customdata}<br>Facturacion: %{y:,.0f}<extra></extra>",
    )
    fig.add_scatter(
        x=cortos, y=top["acumulado_pct"],
        mode="lines", yaxis="y2", name="% acumulado",
        line=dict(color=COLOR_ALERTA, width=2.2), customdata=nombres,
        hovertemplate="%{customdata}<br>Acumulado: %{y:.1f}%<extra></extra>",
    )
    fig.add_hline(y=80, line=dict(color=COLOR_OK, width=1.5, dash="dash"), yref="y2")
    fig.update_layout(
        xaxis=dict(tickmode="array", tickvals=pos,
                   ticktext=[cortos[i] for i in pos],
                   tickangle=-60, title_text="Producto (60 mas facturados)"),
        yaxis=dict(title_text="Facturacion", tickformat=_eje_s(), gridcolor="#ECEFF1"),
        yaxis2=dict(title_text="% acumulado", overlaying="y", side="right", range=[0, 105],
                    showgrid=False, ticksuffix="%",
                    tickfont=dict(color=COLOR_ALERTA),
                    title_font=dict(color=COLOR_ALERTA)),
    )
    n80 = int(d["productos_hasta_80"].iloc[0])
    p80 = float(d["pct_productos_hasta_80"].iloc[0])
    # La nota va dentro del area de trazado (esquina superior izquierda): el pie
    # se montan sobre las etiquetas rotadas del eje x en este grafico.
    fig.add_annotation(text=f"<b>{n80} de {len(d)} productos ({p80:.1f}%) = 80% de la venta</b>",
                       xref="paper", yref="paper", x=0.97, y=0.97, xanchor="right",
                       yanchor="top", showarrow=False, font=dict(size=11, color="#455A64"),
                       bgcolor="white", bordercolor="#CFD8DC", borderpad=5)
    return fig


# --------------------------------------------------------------------------
# 5. Segmentacion de clientes
# --------------------------------------------------------------------------
def grafico_segmentos(d: pd.DataFrame) -> go.Figure:
    fig = _fig(
        "Segmentacion de clientes (RFM)",
        "Barras: numero de clientes por segmento. Hover: participacion en la venta.",
    )
    if d.empty:
        return _vacio(fig, "sin segmentos")
    d = d.reset_index(drop=True)
    tono = {
        "Campeones": "#2E7D32", "Leales": "#66BB6A", "Potenciales": "#9CCC65",
        "Nuevos": "#42A5F5", "En riesgo": "#FFA726", "Dormidos": "#B0BEC5",
    }
    fig.add_bar(
        x=d["segmento"], y=d["clientes"],
        marker_color=[tono.get(s, COLOR_NEUTRO) for s in d["segmento"]],
        text=[f"{n:,}" for n in d["clientes"]], textposition="outside",
        customdata=d["participacion_pct"],
        hovertemplate="%{x}<br>Clientes: %{y:,}<br>Participacion en la facturacion: %{customdata:.1f}%<extra></extra>",
    )
    fig.update_layout(
        yaxis=dict(title_text="Clientes", gridcolor="#ECEFF1"),
    )
    campeones_leales = float(d.loc[d["segmento"].isin(["Campeones", "Leales"]), "participacion_pct"].sum())
    _pie(fig, f"Campeones + Leales concentran {campeones_leales:.1f}% de la facturacion. "
              f"Hover sobre cada barra para ver la participacion.")
    return fig


# --------------------------------------------------------------------------
# 6. Embudo
# --------------------------------------------------------------------------
def grafico_embudo(d: pd.DataFrame) -> go.Figure:
    fig = _fig(
        "Embudo de navegacion a compra",
        "Todos los pasos en la misma unidad: numero de eventos.",
        alto=500,
    )
    if d.empty:
        return _vacio(fig, "sin eventos de navegacion")
    fig.add_bar(
        orientation="h", x=d["eventos"], y=d["paso"],
        marker_color=PALETA[: len(d)],
        text=[f"{e:,}  ({p:.0f}% del inicio)"
              for e, p in zip(d["eventos"], d["participacion_pct"])],
        textposition="outside",
        hovertemplate="%{y}<br>Eventos: %{x:,}<extra></extra>",
    )
    fig.update_layout(
        xaxis=dict(title_text="Eventos", tickformat=_eje_s(), gridcolor="#ECEFF1",
                   range=[0, d["eventos"].max() * 1.45]),
        yaxis=dict(autorange="reversed", tickfont=dict(size=11)),
    )
    caidas = d["caida_vs_paso_anterior_pct"].dropna()
    if len(caidas):
        _pie(fig, " | ".join(f"caida al paso siguiente: {v:.0f}%" for v in caidas))
    return fig


# --------------------------------------------------------------------------
# 7. Correlacion visitas / ventas
# --------------------------------------------------------------------------
def grafico_correlacion(detalle: pd.DataFrame, metricas: pd.DataFrame) -> go.Figure:
    fig = _fig(
        "La navegacion predice la venta?",
        "Cada punto es un producto. Eje x: visualizaciones. Eje y: unidades vendidas.",
    )
    if detalle.empty:
        return _vacio(fig, "sin datos de navegacion")
    v = detalle["numero_visualizaciones"].astype(float)
    u = detalle["cantidad_vendida"].astype(float)
    sizes = 5 + 16 * (u / u.max() if u.max() else 1)
    fig.add_scatter(
        x=v, y=u, mode="markers", name="Productos",
        marker=dict(size=sizes, color=np.where(u > 0, PALETA[0], COLOR_ALERTA),
                    opacity=0.4, line=dict(width=0)),
        customdata=np.stack([detalle.get("nombre", pd.Series([""] * len(detalle))).astype(str)], axis=-1)
        if "nombre" in detalle.columns else None,
        hovertemplate="%{customdata[0]}<br>Visualizaciones: %{x}<br>Unidades: %{y}<extra></extra>",
    )
    sub = detalle[(v > 0) & (u > 0)]
    if len(sub) > 2:
        pendiente, intercepto = np.polyfit(sub["numero_visualizaciones"],
                                           sub["cantidad_vendida"], 1)
        xs = np.linspace(0, float(v.max()), 50)
        fig.add_scatter(
            x=xs, y=intercepto + pendiente * xs, mode="lines", name="Ajuste lineal",
            line=dict(color=COLOR_ALERTA, width=2, dash="dash"),
            hovertemplate="Ajuste: y = %{y:.2f}<extra></extra>",
        )
        fig.add_annotation(
            text=f"ajuste lineal (solo visitados y vendidos)<br>pendiente = {pendiente:.2f} unidades/visita",
            xref="paper", yref="paper", x=0.5, y=0.97, xanchor="center", yanchor="top",
            showarrow=False, font=dict(size=11, color=COLOR_ALERTA),
            bgcolor="white", bordercolor="#FFCDD2", borderpad=6,
        )
    fig.update_layout(
        xaxis=dict(title_text="Visualizaciones del producto", gridcolor="#ECEFF1"),
        yaxis=dict(title_text="Unidades vendidas", gridcolor="#ECEFF1"),
    )
    cero = int((detalle["cantidad_vendida"] == 0).sum())
    lineas = [f"{_cortar(r.metrica, 38)}: {r.valor:.3f}" for r in metricas.itertuples()
              if r.metrica.startswith(("Pearson", "Spearman"))]
    _pie(fig, " | ".join(lineas)
              + f" | {cero} productos con visitas y cero venta (rojo)")
    return fig


# --------------------------------------------------------------------------
# 8-9. Inventario muerto y under-exposure
# --------------------------------------------------------------------------
def grafico_inventario_muerto(d: pd.DataFrame) -> go.Figure:
    fig = _fig(
        "Inversion que no convierte: visitas sin ninguna venta",
        "Productos que reciben trafico y no registran una sola unidad vendida.",
        alto=620,
    )
    if d.empty:
        return _vacio(fig, "todo el trafico navega productos que despues venden")
    total_muertos = int((d["cantidad_vendida"] == 0).sum())
    d = d.head(15).reset_index(drop=True)
    fig.add_bar(
        orientation="h",
        x=d["numero_visualizaciones"],
        y=[_cortar(f"{r.nombre} ({_cortar(r.categoria, 12)})", 40) for r in d.itertuples()],
        marker_color=COLOR_ALERTA,
        hovertemplate="%{y}<br>Visualizaciones: %{x:,}<extra></extra>",
    )
    fig.update_layout(
        xaxis=dict(title_text="Visualizaciones", tickformat=_eje_s(), gridcolor="#ECEFF1"),
        yaxis=dict(autorange="reversed", tickfont=dict(size=10)),
    )
    _pie(fig, f"Mostrados los {len(d)} con mas trafico, de {total_muertos} productos "
              f"que reciben visitas y no registran ninguna unidad vendida")
    return fig


def grafico_under_exposure(d: pd.DataFrame) -> go.Figure:
    fig = _fig(
        "Under-exposure: se vende mucho con pocas visitas",
        "Top 15 por unidades vendidas, con su trafico real.",
        alto=620,
    )
    if d.empty:
        return _vacio(fig, "sin ventas para comparar")
    d = d.head(15).reset_index(drop=True)
    fig.add_bar(
        orientation="h", x=d["cantidad_vendida"],
        y=[_cortar(f"{r.nombre} ({_cortar(r.categoria, 12)})", 40) for r in d.itertuples()],
        marker_color=COLOR_OK,
        hovertemplate="%{y}<br>Unidades vendidas: %{x:,}<extra></extra>",
    )
    fig.update_layout(
        xaxis=dict(title_text="Unidades vendidas", tickformat=_eje_s(), gridcolor="#ECEFF1"),
        yaxis=dict(autorange="reversed", tickfont=dict(size=10)),
    )
    _pie(fig, "visitas por unidad (top 3): " + " | ".join(
        f"{_cortar(r.nombre, 26)} = {r.visitas_por_unidad:.2f}"
        for r in d.head(3).itertuples()
    ))
    return fig


# --------------------------------------------------------------------------
# 10. Descuentos
# --------------------------------------------------------------------------
def grafico_descuentos(d: pd.DataFrame) -> go.Figure:
    fig = _fig(
        "Los descuentos se pagan con margen",
        "Barras: margen real por rango de descuento del pedido.",
    )
    if d.empty:
        return _vacio(fig, "sin ventas con descuento")
    d = d.reset_index(drop=True)
    fig.add_bar(
        x=d["rango_descuento"].astype(str), y=d["margen_pct"].astype(float),
        marker_color=[COLOR_ALERTA if (pd.notna(v) and v < 25) else PALETA[0]
                      for v in d["margen_pct"]],
        text=[f"{v:.1f}%" if pd.notna(v) else "" for v in d["margen_pct"]],
        textposition="outside", customdata=d["unidades"],
        hovertemplate="%{x}<br>Margen: %{y:.1f}%<br>Lineas: %{customdata:,}<extra></extra>",
    )
    tope = float(pd.to_numeric(d["margen_pct"], errors="coerce").max() or 0)
    fig.update_layout(
        yaxis=dict(title_text="Margen real %", ticksuffix="%", gridcolor="#ECEFF1",
                   range=[0, max(tope * 1.25, 10)]),
    )
    _pie(fig, " | ".join(
        f"{r.rango_descuento}: -{r.descuento_pct_del_ingreso:.1f}% del ingreso"
        for r in d.itertuples() if pd.notna(r.descuento_pct_del_ingreso)
    ))
    return fig


# --------------------------------------------------------------------------
# 11. Satisfaccion
# --------------------------------------------------------------------------
def grafico_satisfaccion(d: pd.DataFrame) -> go.Figure:
    fig = _fig(
        "Distribucion de calificaciones",
        "Numero de resenas por estrellas y tasa de positiva.",
    )
    if d.empty:
        return _vacio(fig, "sin resenas")
    d = d.reset_index(drop=True)
    fig.add_bar(
        x=[f"{c:.0f} estrellas" for c in d["calificacion"]], y=d["resenas"],
        marker_color=[COLOR_OK if c >= 4 else (COLOR_ALERTA if c <= 2 else PALETA[1])
                      for c in d["calificacion"]],
        text=[f"{n:,}<br>{p:.0f}% del total"
              for n, p in zip(d["resenas"], d["participacion_pct"])],
        textposition="outside",
        hovertemplate="%{x}<br>Resenas: %{y:,}<extra></extra>",
    )
    fig.update_layout(
        yaxis=dict(title_text="Resenas", gridcolor="#ECEFF1"),
        xaxis=dict(tickfont=dict(size=11)),
    )
    total = int(d["resenas"].sum())
    positivas = int(d["positivas"].sum())
    _pie(fig, f"total {numero(total)} resenas | "
              f"{positivas / max(total, 1) * 100:.1f}% positivas (4-5 estrellas) | "
              f"{numero(d['verificadas'].sum())} verificadas")
    return fig


# --------------------------------------------------------------------------
# 12. Sucursales
# --------------------------------------------------------------------------
def grafico_sucursales(d: pd.DataFrame) -> go.Figure:
    fig = _fig(
        "Facturacion por sucursal",
        "Cada barra es una sucursal fisica; el color es su region.",
    )
    if d.empty:
        return _vacio(fig, "sin ventas por sucursal")
    d = d.sort_values("facturacion", ascending=True)
    tono_region = {"Sureste": "#55A868", "Centro": "#4C72B0",
                   "Occidente": "#DD8452", "Norte": "#8172B3", "Nacional": COLOR_NEUTRO}
    colores = [tono_region.get(r, COLOR_NEUTRO) for r in d["region"]]
    etiquetas = [f"{_cortar(c, 18)} ({i})" for c, i in zip(d["ciudad"], d["id_sucursal"])] \
        if "ciudad" in d.columns else [str(i) for i in d["id_sucursal"]]
    maximo = float(d["facturacion"].max())
    fig.add_bar(
        orientation="h", x=d["facturacion"], y=etiquetas, marker_color=colores,
        text=[f"ticket {numero(v)}" for v in d["ticket_promedio"]], textposition="outside",
        customdata=list(d["nombre"].astype(str) + " · " + d["region"].astype(str)) if "nombre" in d.columns else None,
        hovertemplate="%{customdata}<br>Facturacion: %{x:,.0f}<extra></extra>" if "nombre" in d.columns
        else "%{y}<br>Facturacion: %{x:,.0f}<extra></extra>",
    )
    fig.update_layout(
        xaxis=dict(title_text="Facturacion", tickformat=_eje_s(), gridcolor="#ECEFF1",
                   range=[0, maximo * 1.32]),
        yaxis=dict(tickfont=dict(size=11)),
    )
    return fig


# --------------------------------------------------------------------------
# 13. Ciudades
# --------------------------------------------------------------------------
def grafico_ciudades(d: pd.DataFrame) -> go.Figure:
    fig = _fig(
        "Ventas por ciudad",
        "Barras: facturacion de pedidos completados. Etiqueta: participacion del total.",
    )
    if d.empty:
        return _vacio(fig, "sin ventas por ciudad")
    d = d.sort_values("facturacion", ascending=True)
    fig.add_bar(
        orientation="h", x=d["facturacion"], y=[_cortar(s, 22) for s in d["segmento"]],
        marker_color=[PALETA[i % len(PALETA)] for i in range(len(d))],
        text=[f"{v:.1f}%" for v in d["participacion_pct"]], textposition="outside",
        hovertemplate="%{y}<br>Facturacion: %{x:,.0f}<extra></extra>",
    )
    fig.update_layout(
        xaxis=dict(title_text="Facturacion", tickformat=_eje_s(), gridcolor="#ECEFF1"),
        yaxis=dict(tickfont=dict(size=11)),
    )
    _pie(fig, " | ".join(
        f"{_cortar(r.segmento, 18)}: {numero(r.facturacion)}"
        for r in d.sort_values("facturacion", ascending=False).itertuples()
    ))
    return fig


# --------------------------------------------------------------------------
# Orquestacion
# --------------------------------------------------------------------------
GRAFICOS = [
    # Bloque principal (1-7): los que se presentan y se defienden en 10 segundos.
    ("01_ventas_mensuales", "Serie temporal de ventas", "principales",
     lambda r: grafico_ventas_mensuales(r["02_ventas_mensuales"])),
    ("02_mix_categoria", "Mix por categoria", "principales",
     lambda r: grafico_mix_categoria(r["03_mix_categoria"])),
    ("03_ley_de_pareto", "Ley de Pareto", "principales",
     lambda r: grafico_pareto(r["15_ley_pareto"])),
    ("04_embudo_navegacion", "Embudo navegacion-compra", "principales",
     lambda r: grafico_embudo(r["09_embudo_navegacion"])),
    ("05_inventario_muerto", "Visitas sin venta", "principales",
     lambda r: grafico_inventario_muerto(r["13_inventario_muerto"])),
    ("06_impacto_descuentos", "Descuentos vs margen", "principales",
     lambda r: grafico_descuentos(r["17_impacto_descuentos"])),
    ("07_ventas_por_ciudad", "Ventas por ciudad", "principales",
     lambda r: grafico_ciudades(r["21_ventas_por_ciudad"])),
    # Anexo (8-13): respaldo completo, para el reporte y las preguntas del jurado.
    ("08_ticket_por_canal", "Ticket y margen por canal", "anexo",
     lambda r: grafico_ticket_canal(r["04_mix_canal"])),
    ("09_segmentos_clientes", "Segmentacion RFM", "anexo",
     lambda r: grafico_segmentos(r["07_segmentos_clientes"])),
    ("10_correlacion_visitas_ventas", "Correlacion navegacion-venta", "anexo",
     lambda r: grafico_correlacion(r["12_dispersion_visitas_ventas"], r["11_correlacion_visitas_ventas"])),
    ("11_under_exposure", "Under-exposure", "anexo",
     lambda r: grafico_under_exposure(r["14_under_exposure"])),
    ("12_satisfaccion", "Calificaciones", "anexo",
     lambda r: grafico_satisfaccion(r["18_satisfaccion"])),
    ("13_por_sucursal", "Facturacion por sucursal", "anexo",
     lambda r: grafico_sucursales(r["06_por_sucursal"])),
]


def _guardar(fig: go.Figure, nombre: str, destino: Path) -> Path:
    """Exporta una figura a HTML. La primera escribe `plotly.min.js` en la
    carpeta (modo `directory`) y las siguientes lo reutilizan: 13 paginas
    pequenas + una sola copia de la libreria, todo offline."""
    ruta = destino / f"{nombre}.html"
    fig.write_html(ruta, include_plotlyjs="directory", full_html=True)
    return ruta


def _reporte_html(figuras: list[tuple[str, str, str, go.Figure]], destino: Path) -> Path:
    """Una sola pagina con las 13 figuras. Reutiliza `plotly.min.js` que cada
    figura individual ya escribio en `data/figures/` (ruta relativa
    `../figures/plotly.min.js`), asi que este HTML pesa unos pocos KB."""
    principales = [f for f in figuras if f[2] == "principales"]
    anexo = [f for f in figuras if f[2] == "anexo"]

    trozos = []
    for i, (nombre, titulo_gr, _, fig) in enumerate(figuras, start=1):
        if i == 1:
            trozos.append('<h3 class="bloque">Principales (1-7)</h3>')
        elif i == len(principales) + 1:
            trozos.append('<h3 class="bloque">Anexo (8-13)</h3>')
        cuerpo = fig.to_html(full_html=False, include_plotlyjs=False,
                             div_id=f"g{i}", config={"displaylogo": False})
        trozos.append(
            f'<section id="{nombre}"><h2>{i}. {titulo_gr}</h2>{cuerpo}</section>'
        )

    def _indice(grupo):
        return "".join(f'<li><a href="#{n}">{t}</a></li>' for n, t, _, _ in grupo)

    indice = (
        '<div class="bloque-nav">Principales</div>'
        f'<ol start="1">{_indice(principales)}</ol>'
        '<div class="bloque-nav">Anexo</div>'
        f'<ol start="{len(principales) + 1}">{_indice(anexo)}</ol>'
    )
    doc = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Reporte de analisis - {EMPRESA}</title>
<script src="../figures/plotly.min.js"></script>
<style>
  body {{ font-family: {_FUENTE}; margin: 0; color: #263238; background: #FAFAFA; }}
  header {{ background: #263238; color: #fff; padding: 28px 40px; }}
  header h1 {{ margin: 0 0 6px; font-size: 24px; }}
  header p {{ margin: 0; color: #B0BEC5; }}
  nav {{ padding: 16px 40px; background: #fff; border-bottom: 1px solid #ECEFF1; }}
  nav ol {{ margin: 4px 0 10px; padding-left: 20px; columns: 2; }}
  nav .bloque-nav {{ font-size: 12px; text-transform: uppercase; letter-spacing: 1px;
                     color: #607D8B; margin-top: 8px; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 8px 24px 60px; }}
  h3.bloque {{ max-width: 1100px; margin: 28px auto 0; padding: 0 24px;
               font-size: 15px; text-transform: uppercase; letter-spacing: 1px;
               color: #607D8B; border-bottom: 2px solid #CFD8DC; padding-bottom: 6px; }}
  section {{ background: #fff; border: 1px solid #ECEFF1; border-radius: 8px;
             padding: 8px 20px 20px; margin: 24px 0; }}
  section h2 {{ font-size: 16px; color: #455A64; }}
</style>
</head>
<body>
<header>
  <h1>Reporte de analisis - {EMPRESA}</h1>
  <p>{len(figuras)} visualizaciones interactivas (plotly). Pasa el mouse para ver el valor exacto.</p>
</header>
<nav>{indice}</nav>
<main>{''.join(trozos)}</main>
</body>
</html>
"""
    destino.write_text(doc, encoding="utf-8")
    return destino


def construir_todos(resultados: dict[str, pd.DataFrame], destino: Path | None = None,
                    reporte: Path | None = None) -> pd.DataFrame:
    destino = asegurar_dir(destino or FIGURES)
    figuras: list[tuple[str, str, str, go.Figure]] = []
    indice = []
    for nombre, titulo_gr, bloque, fn in GRAFICOS:
        try:
            fig = fn(resultados)
            ruta = _guardar(fig, nombre, destino)
            kb = ruta.stat().st_size / 1024
            figuras.append((nombre, titulo_gr, bloque, fig))
            indice.append({"grafico": nombre, "titulo": titulo_gr, "archivo": ruta.name,
                           "estado": "OK", "kb": round(kb, 1), "error": ""})
        except Exception as exc:  # noqa: BLE001 - un grafico roto no debe tumbar el pipeline
            indice.append({"grafico": nombre, "titulo": titulo_gr, "archivo": "",
                           "estado": "ERROR", "kb": 0.0, "error": f"{type(exc).__name__}: {exc}"})
    if figuras:
        ruta_reporte = _reporte_html(figuras, asegurar_dir(reporte or REPORTS) / "reporte.html")
        LOG.info("  Reporte combinado -> %s", ruta_reporte)
    return pd.DataFrame(indice)


def main() -> None:
    print(titulo("GRAFICOS DEL REPORTE"))
    asegurar_dir(FIGURES)
    # Mismo motivo que en analysis: una figura renombrada dejaba su HTML viejo.
    # Tambien se limpian los *.png de la version anterior (matplotlib).
    for viejo in list(FIGURES.glob("*.html")) + list(FIGURES.glob("*.png")):
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

    destino_indice = REPORTS / "figuras_indice.csv"
    indice.to_csv(destino_indice, index=False, encoding="utf-8-sig")
    LOG.info("  %d graficos -> %s", len(indice), FIGURES)
    LOG.info("  Indice -> %s", destino_indice)

    fallidos = indice[indice.estado != "OK"]
    if len(fallidos):
        for f in fallidos.itertuples():
            LOG.error("  %s: %s", f.archivo or f.grafico, f.error)
        raise AssertionError(f"{len(fallidos)} graficos fallaron")
    LOG.info("  Todos los graficos generados sin error")


if __name__ == "__main__":
    main()
