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
- Enviar una búsqueda semántica que consulta el índice vectorial y devuelve hasta 5 resultados relevantes.
