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

# Probar el índice 
python local-test.py "nuggets para desayuno" --k 5 --filter-available true --max-price 8

# Ejecutar la aplicación web
python app.py
