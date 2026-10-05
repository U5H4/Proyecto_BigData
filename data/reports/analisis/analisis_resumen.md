# Resumen del analisis

Generado automaticamente por `src/analysis.py`.

## KPIs

| Indicador | Valor | Nota |
|---|---|---|
| Facturacion | $127,336,206.51 | solo pedidos completados |
| Pedidos totales | 2,259 | unicos, no lineas |
| Pedidos completados | 1,483 |  |
| Tasa de cancelacion | 34.35% | pedidos cancelados / pedidos totales |
| Unidades vendidas | 10,782 |  |
| Ticket promedio | $85,863.93 | facturacion / pedidos completados |
| Unidades por pedido | 7.27 |  |
| Clientes | 1,314 | con al menos un pedido |
| Productos vendidos | 514 |  |
| Categorias | 6 |  |
| Utilidad bruta | $37,982,053.12 | ingreso - costo - descuentos |
| Margen real ponderado | 29.46% | utilidad / ingreso bruto |
| Descuentos otorgados | $1,574,292.30 |  |
| Ticket con descuento | $48,090.66 | solo lineas con descuento |
| Ticket sin descuento | $50,042.85 |  |
| Ingreso por cliente | $96,907.31 |  |

## Segmentacion de clientes

| Segmento | Clientes | Facturacion | % del total | Regla |
|---|---|---|---|---|
| Campeones | 137 | $41,565,349.67 | 32.6% | R>=4 y F>=4 y M>=4: compran reciente, frecuente y alto |
| Leales | 291 | $50,592,499.29 | 39.7% | F>=3 y M>=3: compran bien pero hace tiempo |
| Potenciales | 178 | $3,304,755.98 | 2.6% | F>=3: compran algo, gasto bajo |
| Nuevos | 56 | $3,600,033.91 | 2.8% | R=5 y F<=2: sealiens hace poco y aun repiten |
| En riesgo | 152 | $25,028,032.85 | 19.7% | F<=2 y M>=3: gastaron mucho y ya no vuelven |
| Dormidos | 196 | $3,245,534.81 | 2.5% | el resto: baja frecuencia y bajo gasto |

## Navegacion -> venta

| Metrica | Valor | Nota |
|---|---|---|
| Pearson (todos los productos) | 0.1463 | incluye los que nadie vio y los que nadie compro |
| Pearson (solo visitados) | 0.1038 | responde: si lo ven, lo compran? |
| Pearson (visitados y vendidos) | 0.3234 | es la que calcula el pipeline A10; premia al bestseller |
| Spearman (todos los productos) | 0.2701 | rango: inmune a los valores extremos |
| Spearman (solo visitados) | 0.2756 |  |
| Productos visitados | 455.0000 | con al menos una visualizacion |
| Productos visitados y vendidos | 392.0000 |  |
| Productos sin ninguna visita | 122.0000 | venta que la navegacion no puede explicar |

## Concentracion

- **124 de 514 productos** (24.1% del catalogo vendido) explican el 80% de la facturacion.
- **63 productos** reciben visitas y no registran ni una venta.
