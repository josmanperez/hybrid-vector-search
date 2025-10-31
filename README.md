# DUMP
En la carpeta `/dump` se encuentra un mongodump de la base de datos. De forma que si usamos VoyageAI no tendríamos que generar los vectores de nuevo.

# `.env`
Crear un archivo `.env` copiando el archivo `env.sample` y rellenar las variables necesarias.

# Lanzar el enviroment 
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Cargar el seed (NO NECESARIO SI SE HIZO UN MONGORESTORE)
python seed.py --drop --count 1000 

# Aplanar la matriz para preparar los datos que se van a consultar. (NO NECESARIO SI SE HIZO UN MONGORESTORE)
python transform-seed.py --drop-target

# Cargar los embeddings (NO NECESARIO SI SE HIZO UN MONGORESTORE)
python embed.py --skip-existing

# Crear el índices
python indexes.py --replace --num-dimensions 1024
> Nota: el script crea/reemplaza tanto el índice vectorial como el índice de búsqueda de texto completo.

# Probar el índice 
python local-test.py "nuggets para desayuno" --k 5 --filter-available true --max-price 8

# Ejecutar la aplicación web
python app.py

La interfaz web permite:
- Autocompletar el listado de restaurantes disponibles desde la colección `product_detail`.
- Activar filtros opcionales de disponibilidad, restaurante y precio máximo (habilitando el slider).
- Elegir entre búsqueda vectorial, híbrida (score fusion) o full text directa sobre el campo `title`.
- Enviar una búsqueda semántica que devuelve hasta 5 resultados relevantes según el modo seleccionado.

## Registro de operaciones
- Cada script registra sus acciones en `logs/log-<timestamp>.log` (ruta configurable con `LOG_DIR`).
- Encontrarás trazas para creación/eliminación de índices, generación de embeddings, transformaciones y consultas ejecutadas desde el backend Flask.
