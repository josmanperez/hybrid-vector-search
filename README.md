# Lanzar el enviroment 
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt 

# Cargar el seed
python seed.py --drop --count 1000 

# Flatten array to prepare data to be queried
python transform-seed.py --drop-target

# Cargar los embeddings
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
- Elegir entre búsqueda vectorial, híbrida (rank fusion) o full text directa sobre el campo `title`.
- Enviar una búsqueda semántica que devuelve hasta 5 resultados relevantes según el modo seleccionado.

## Registro de operaciones
- Cada script registra sus acciones en `logs/log-<timestamp>.log` (ruta configurable con `LOG_DIR`).
- Encontrarás trazas para creación/eliminación de índices, generación de embeddings, transformaciones y consultas ejecutadas desde el backend Flask.
