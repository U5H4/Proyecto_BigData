// Consultas find/countDocuments Corporativo JUC (B01-B15)
// Generadas: 2026-10-18 14:11:46
// Ejecutar con mongosh sobre la base de datos NoSQL (ver MONGO_DB en src/config.py)

// B01: Productos premium (precio > 5000)
// Pregunta: Que articulos de gama alta tenemos?
db.productos.find({"precio": {"$gt": 5000}}, {"id_producto": 1, "nombre": 1, "categoria": 1, "precio": 1, "rango_precio": 1, "_id": 0})
  .sort({"precio": -1})
  .limit(10)

// B02: Productos economicos (precio < 1000)
// Pregunta: Que opciones de bajo costo hay?
db.productos.find({"precio": {"$lt": 1000}}, {"id_producto": 1, "nombre": 1, "categoria": 1, "precio": 1, "_id": 0})
  .sort({"precio": 1})
  .limit(10)

// B03: Catalogo de Computadoras y Monitores
// Pregunta: Que hay en las categorias de mayor ticket?
db.productos.find({"categoria": {"$in": ["Computadoras", "Monitores"]}}, {"id_producto": 1, "nombre": 1, "categoria": 1, "precio": 1, "_id": 0})
  .sort({"precio": -1})
  .limit(15)

// B04: Rango Alto y menos de 30000 ($and)
// Pregunta: Que productos caros siguen siendo alcanzables?
db.productos.find({"$and": [{"rango_precio": "Alto"}, {"precio": {"$lt": 30000}}]}, {"id_producto": 1, "nombre": 1, "precio": 1, "rango_precio": 1, "_id": 0})
  .sort({"precio": -1})
  .limit(10)

// B05: Redes o Accesorios ($or)
// Pregunta: Cual es el surtido de conectividad y perifericos?
db.productos.find({"$or": [{"categoria": "Redes"}, {"categoria": "Accesorios"}]}, {"id_producto": 1, "nombre": 1, "categoria": 1, "precio": 1, "_id": 0})
  .sort({"nombre": 1})
  .limit(20)

// B06: Banda de precio 1000-5000 ($gte/$lte)
// Pregunta: Cual es el corazon del catalogo?
db.productos.find({"precio": {"$gte": 1000, "$lte": 5000}}, {"id_producto": 1, "nombre": 1, "categoria": 1, "precio": 1, "_id": 0})
  .sort({"precio": 1})
  .limit(15)

// B07: Resenas de 5 estrellas ($gt)
// Pregunta: Que opiniones sobresalientes hay?
db.resenas.find({"calificacion": {"$gt": 4}}, {"id_resena": 1, "id_producto": 1, "producto": 1, "calificacion": 1, "fecha": 1, "_id": 0})
  .sort({"fecha": -1})
  .limit(20)

// B08: Resenas negativas ($lt)
// Pregunta: Que productos estan generando insatisfaccion?
db.resenas.find({"calificacion": {"$lt": 3}}, {"id_resena": 1, "id_producto": 1, "producto": 1, "calificacion": 1, "comentario": 1, "_id": 0})
  .sort({"calificacion": 1})
  .limit(20)

// B09: Resenas 1 y 2 estrellas ($in)
// Pregunta: Cuales son las quejas duras?
db.resenas.find({"calificacion": {"$in": [1, 2]}}, {"id_resena": 1, "producto": 1, "calificacion": 1, "comentario": 1, "_id": 0})
  .sort({"fecha": -1})
  .limit(25)

// B10: Resenas buenas y verificadas ($and)
// Pregunta: Que alabanzas vienen de compras confirmadas?
db.resenas.find({"$and": [{"calificacion": {"$gte": 4}}, {"verificada": true}]}, {"id_resena": 1, "producto": 1, "calificacion": 1, "verificada": 1, "fecha": 1, "_id": 0})
  .sort({"fecha": -1})
  .limit(20)

// B11: Resenas extremas 1 o 5 ($or)
// Pregunta: Que productos polarizan la opinion?
db.resenas.find({"$or": [{"calificacion": 1}, {"calificacion": 5}]}, {"id_resena": 1, "producto": 1, "calificacion": 1, "es_positiva": 1, "_id": 0})
  .sort({"fecha": -1})
  .limit(20)

// B12: Visualizaciones largas (>300s) ($and/$gt)
// Pregunta: Que productos retienen la atencion?
db.actividad_usuario.find({"$and": [{"es_visualizacion": true}, {"duracion_seg": {"$gt": 300}}]}, {"usuario": 1, "producto": 1, "nombre_producto": 1, "duracion_seg": 1, "fecha": 1, "_id": 0})
  .sort({"duracion_seg": -1})
  .limit(20)

// B13: Conteo de compras registradas (countDocuments)
// Pregunta: Cuantos eventos de compra hay en total?
db.actividad_usuario.countDocuments({"evento": "producto_comprado"})

// B14: Navegacion desde equipos Apple ($in)
// Pregunta: Como navega el usuario de ecosistema Apple?
db.actividad_usuario.find({"dispositivo": {"$in": ["iOS", "macOS"]}}, {"usuario": 1, "producto": 1, "dispositivo": 1, "duracion_seg": 1, "fecha": 1, "_id": 0})
  .sort({"fecha": -1})
  .limit(20)

// B15: Sesiones muy cortas o muy largas ($or)
// Pregunta: Donde el engagement es anomalo?
db.actividad_usuario.find({"$or": [{"duracion_seg": {"$lt": 30}}, {"duracion_seg": {"$gt": 1200}}]}, {"usuario": 1, "producto": 1, "evento": 1, "duracion_seg": 1, "_id": 0})
  .sort({"duracion_seg": -1})
  .limit(25)

