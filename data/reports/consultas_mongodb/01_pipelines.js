// Pipelines de agregacion Corporativo JUC
// Generados: 2026-11-09 07:05:09
// Ejecutar con mongosh / mongodump sobre la base de datos NoSQL (ver MONGO_DB en src/config.py)

// A01: Top 10 productos mas vistos
// Pregunta: Que productos concentran la atencion?
db.actividad_usuario.aggregate(
[
  {
    "$match": {
      "es_visualizacion": true
    }
  },
  {
    "$group": {
      "_id": "$producto",
      "visitas": {
        "$sum": 1
      },
      "usuarios": {
        "$addToSet": "$usuario"
      },
      "categorias": {
        "$first": "$categoria"
      }
    }
  },
  {
    "$addFields": {
      "usuarios_unicos": {
        "$size": "$usuarios"
      }
    }
  },
  {
    "$sort": {
      "visitas": -1,
      "_id": 1
    }
  },
  {
    "$limit": 10
  },
  {
    "$project": {
      "_id": 0,
      "producto": "$_id",
      "visitas": 1,
      "usuarios_unicos": 1,
      "categoria": "$categorias"
    }
  }
]
)

// A02: Productos vistos muchas veces y NUNCA vendidos
// Pregunta: Cual es la inversion publicitaria que no convierte?
db.actividad_usuario.aggregate(
[
  {
    "$match": {
      "es_visualizacion": true
    }
  },
  {
    "$group": {
      "_id": "$producto",
      "visitas": {
        "$sum": 1
      },
      "nombre": {
        "$first": "$nombre_producto"
      },
      "categoria": {
        "$first": "$categoria"
      }
    }
  },
  {
    "$sort": {
      "visitas": -1,
      "_id": 1
    }
  },
  {
    "$limit": 150
  },
  {
    "$lookup": {
      "from": "productos",
      "localField": "_id",
      "foreignField": "id_producto",
      "as": "ficha"
    }
  },
  {
    "$addFields": {
      "unidades_vendidas": {
        "$ifNull": [
          {
            "$arrayElemAt": [
              "$ficha.unidades_vendidas",
              0
            ]
          },
          0
        ]
      },
      "ingresos": {
        "$ifNull": [
          {
            "$arrayElemAt": [
              "$ficha.ingresos",
              0
            ]
          },
          0
        ]
      }
    }
  },
  {
    "$match": {
      "unidades_vendidas": 0
    }
  },
  {
    "$sort": {
      "visitas": -1,
      "_id": 1
    }
  },
  {
    "$project": {
      "_id": 0,
      "producto": "$_id",
      "nombre": 1,
      "categoria": 1,
      "visitas": 1,
      "unidades_vendidas": 1,
      "ingresos": 1
    }
  }
]
)

// A03: Productos vendidos pese a ser poco vistos
// Pregunta: Cual es la under-exposure que nos cuesta venta?
// Nota: El $lookup contra `productos` incrusta las unidades vendidas; asi el cruce navegacion-venta queda resuelto dentro de MongoDB.
db.actividad_usuario.aggregate(
[
  {
    "$match": {
      "es_visualizacion": true
    }
  },
  {
    "$group": {
      "_id": "$producto",
      "visitas": {
        "$sum": 1
      },
      "nombre": {
        "$first": "$nombre_producto"
      },
      "categoria": {
        "$first": "$categoria"
      }
    }
  },
  {
    "$sort": {
      "visitas": 1,
      "_id": 1
    }
  },
  {
    "$limit": 150
  },
  {
    "$lookup": {
      "from": "productos",
      "localField": "_id",
      "foreignField": "id_producto",
      "as": "ficha"
    }
  },
  {
    "$addFields": {
      "unidades_vendidas": {
        "$ifNull": [
          {
            "$arrayElemAt": [
              "$ficha.unidades_vendidas",
              0
            ]
          },
          0
        ]
      },
      "ingresos": {
        "$ifNull": [
          {
            "$arrayElemAt": [
              "$ficha.ingresos",
              0
            ]
          },
          0
        ]
      }
    }
  },
  {
    "$match": {
      "unidades_vendidas": {
        "$gt": 0
      }
    }
  },
  {
    "$sort": {
      "unidades_vendidas": -1,
      "visitas": 1,
      "_id": 1
    }
  },
  {
    "$project": {
      "_id": 0,
      "producto": "$_id",
      "nombre": 1,
      "categoria": 1,
      "visitas": 1,
      "unidades_vendidas": 1,
      "ingresos": 1
    }
  }
]
)

// A04: Distribucion de visitas por mes
// Pregunta: Como se mueve el trafico web?
db.actividad_usuario.aggregate(
[
  {
    "$match": {
      "es_visualizacion": true
    }
  },
  {
    "$group": {
      "_id": {
        "$substr": [
          "$fecha",
          0,
          7
        ]
      },
      "visitas": {
        "$sum": 1
      },
      "usuarios": {
        "$addToSet": "$usuario"
      }
    }
  },
  {
    "$addFields": {
      "usuarios_unicos": {
        "$size": "$usuarios"
      }
    }
  },
  {
    "$sort": {
      "_id": 1
    }
  },
  {
    "$project": {
      "_id": 0,
      "anio_mes": "$_id",
      "visitas": 1,
      "usuarios_unicos": 1
    }
  }
]
)

// A05: Navegacion por categoria y dispositivo
// Pregunta: Que dispositivo prefiere cada categoria?
db.actividad_usuario.aggregate(
[
  {
    "$match": {
      "es_visualizacion": true
    }
  },
  {
    "$group": {
      "_id": {
        "categoria": "$categoria",
        "dispositivo": "$dispositivo"
      },
      "visitas": {
        "$sum": 1
      },
      "duracion_promedio": {
        "$avg": "$duracion_seg"
      }
    }
  },
  {
    "$sort": {
      "visitas": -1,
      "_id": 1
    }
  },
  {
    "$project": {
      "_id": 0,
      "categoria": "$_id.categoria",
      "dispositivo": "$_id.dispositivo",
      "visitas": 1,
      "duracion_promedio": 1
    }
  }
]
)

// A06: Rating promedio y dispersion por producto
// Pregunta: Que tan bien recibidos estan los productos?
db.resenas.aggregate(
[
  {
    "$group": {
      "_id": "$id_producto",
      "rating_promedio": {
        "$avg": "$calificacion"
      },
      "total_resenas": {
        "$sum": 1
      },
      "positivas": {
        "$sum": {
          "$cond": [
            {
              "$gte": [
                "$calificacion",
                4
              ]
            },
            1,
            0
          ]
        }
      },
      "negativas": {
        "$sum": {
          "$cond": [
            {
              "$lte": [
                "$calificacion",
                2
              ]
            },
            1,
            0
          ]
        }
      },
      "ultima_resena": {
        "$max": "$fecha"
      }
    }
  },
  {
    "$addFields": {
      "tasa_negativas": {
        "$round": [
          {
            "$multiply": [
              100,
              {
                "$divide": [
                  "$negativas",
                  "$total_resenas"
                ]
              }
            ]
          },
          2
        ]
      }
    }
  },
  {
    "$sort": {
      "total_resenas": -1,
      "_id": 1
    }
  },
  {
    "$limit": 25
  },
  {
    "$project": {
      "_id": 0,
      "id_producto": "$_id",
      "rating_promedio": 1,
      "total_resenas": 1,
      "positivas": 1,
      "negativas": 1,
      "tasa_negativas": 1,
      "ultima_resena": 1
    }
  }
]
)

// A07: Productos bien valorados y con muchas resenas
// Pregunta: El juicio positivo se sostiene entre productos?
db.resenas.aggregate(
[
  {
    "$match": {
      "calificacion": {
        "$gte": 4
      }
    }
  },
  {
    "$group": {
      "_id": "$id_producto",
      "likes": {
        "$sum": 1
      },
      "rating_promedio": {
        "$avg": "$calificacion"
      }
    }
  },
  {
    "$sort": {
      "likes": -1,
      "_id": 1
    }
  },
  {
    "$limit": 20
  },
  {
    "$project": {
      "_id": 0,
      "id_producto": "$_id",
      "likes": 1,
      "rating_promedio": 1
    }
  }
]
)

// A08: Catalogo por subdocumento de atributos (consulta dinamica)
// Pregunta: Se puede consultar un atributo que solo existe en una familia?
// Nota: Este es el caso de uso que justifica MongoDB: la clave atributos.procesador NO existe en todas las categorias. En PostgreSQL habria que unir una tabla puente producto_atributo o usar JSONB. pd.json_normalize aplana el subdocumento, asi que la columna queda como 'atributos.procesador'.
db.productos.aggregate(
[
  {
    "$match": {
      "atributos.procesador": {
        "$exists": true
      }
    }
  },
  {
    "$group": {
      "_id": "$atributos.procesador",
      "productos": {
        "$sum": 1
      },
      "precio_promedio": {
        "$avg": "$precio"
      },
      "categorias": {
        "$addToSet": "$categoria"
      }
    }
  },
  {
    "$sort": {
      "productos": -1,
      "_id": 1
    }
  }
]
)

// A09: Recorrido del usuario mas activo
// Pregunta: Como se ve la sesion de un cliente que si navego?
// Nota: El usuario se elige con $group+$sort en vez de hardcodear un id: así el pipeline funciona con cualquier dataset. El $lookup sobre la misma coleccion reconstruye el trayecto.
db.actividad_usuario.aggregate(
[
  {
    "$group": {
      "_id": "$usuario",
      "eventos": {
        "$sum": 1
      }
    }
  },
  {
    "$sort": {
      "eventos": -1,
      "_id": 1
    }
  },
  {
    "$limit": 1
  },
  {
    "$lookup": {
      "from": "actividad_usuario",
      "let": {
        "usuario_activo": "$_id"
      },
      "pipeline": [
        {
          "$match": {
            "$expr": {
              "$eq": [
                "$usuario",
                "$$usuario_activo"
              ]
            }
          }
        },
        {
          "$sort": {
            "fecha": 1
          }
        },
        {
          "$limit": 40
        }
      ],
      "as": "trayecto"
    }
  },
  {
    "$unwind": "$trayecto"
  },
  {
    "$replaceRoot": {
      "newRoot": "$trayecto"
    }
  },
  {
    "$project": {
      "_id": 0,
      "fecha": 1,
      "evento": 1,
      "producto": 1,
      "nombre_producto": 1,
      "duracion_seg": 1
    }
  }
]
)

// A10: Correlacion visitas vs ventas por producto
// Pregunta: La navegacion predice la venta (punto 23 del enunciado)?
db.actividad_usuario.aggregate(
[
  {
    "$match": {
      "es_visualizacion": true
    }
  },
  {
    "$group": {
      "_id": "$producto",
      "visitas": {
        "$sum": 1
      },
      "nombre": {
        "$first": "$nombre_producto"
      },
      "categoria": {
        "$first": "$categoria"
      }
    }
  },
  {
    "$lookup": {
      "from": "productos",
      "localField": "_id",
      "foreignField": "id_producto",
      "as": "ficha"
    }
  },
  {
    "$addFields": {
      "unidades_vendidas": {
        "$ifNull": [
          {
            "$arrayElemAt": [
              "$ficha.unidades_vendidas",
              0
            ]
          },
          0
        ]
      },
      "ingresos": {
        "$ifNull": [
          {
            "$arrayElemAt": [
              "$ficha.ingresos",
              0
            ]
          },
          0
        ]
      }
    }
  },
  {
    "$addFields": {
      "vendido": {
        "$gt": [
          "$unidades_vendidas",
          0
        ]
      },
      "ratio_ventas_por_visita": {
        "$round": [
          {
            "$cond": [
              {
                "$gt": [
                  "$visitas",
                  0
                ]
              },
              {
                "$divide": [
                  "$unidades_vendidas",
                  "$visitas"
                ]
              },
              0
            ]
          },
          3
        ]
      }
    }
  },
  {
    "$sort": {
      "vendido": -1,
      "unidades_vendidas": -1,
      "_id": 1
    }
  },
  {
    "$project": {
      "_id": 0,
      "producto": "$_id",
      "nombre": 1,
      "categoria": 1,
      "visitas": 1,
      "unidades_vendidas": 1,
      "ingresos": 1,
      "vendido": 1,
      "ratio_ventas_por_visita": 1
    }
  }
]
)

// A11: Calificacion promedio por categoria de producto
// Pregunta: Que categoria de producto deja mejor (o peor) impresion?
// Nota: El documento de resena ya trae la categoria desnormalizada, asi que basta un $group por categoria; en un esquema normalizado habria que unir resenas -> productos -> categorias.
db.resenas.aggregate(
[
  {
    "$group": {
      "_id": "$categoria",
      "rating_promedio": {
        "$avg": "$calificacion"
      },
      "total_resenas": {
        "$sum": 1
      },
      "positivas": {
        "$sum": {
          "$cond": [
            {
              "$gte": [
                "$calificacion",
                4
              ]
            },
            1,
            0
          ]
        }
      }
    }
  },
  {
    "$addFields": {
      "pct_positivas": {
        "$round": [
          {
            "$multiply": [
              100,
              {
                "$divide": [
                  "$positivas",
                  "$total_resenas"
                ]
              }
            ]
          },
          1
        ]
      }
    }
  },
  {
    "$sort": {
      "rating_promedio": -1,
      "_id": 1
    }
  },
  {
    "$project": {
      "_id": 0,
      "categoria": "$_id",
      "rating_promedio": 1,
      "total_resenas": 1,
      "positivas": 1,
      "pct_positivas": 1
    }
  }
]
)

// A12: Actividad de navegacion por ciudad
// Pregunta: Desde que ciudad se navega mas el catalogo?
// Nota: Agrupa los eventos de navegacion por el campo `ubicacion` del documento (la ciudad del usuario), un atributo que solo tiene sentido en el evento y no en una tabla relacional fija.
db.actividad_usuario.aggregate(
[
  {
    "$match": {
      "es_visualizacion": true
    }
  },
  {
    "$group": {
      "_id": "$ubicacion",
      "eventos": {
        "$sum": 1
      },
      "usuarios": {
        "$addToSet": "$usuario"
      },
      "duracion_promedio": {
        "$avg": "$duracion_seg"
      }
    }
  },
  {
    "$addFields": {
      "usuarios_unicos": {
        "$size": "$usuarios"
      }
    }
  },
  {
    "$sort": {
      "eventos": -1,
      "_id": 1
    }
  },
  {
    "$project": {
      "_id": 0,
      "ubicacion": "$_id",
      "eventos": 1,
      "usuarios_unicos": 1,
      "duracion_promedio": 1
    }
  }
]
)

