import argparse
import os
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Iterable

from bson import ObjectId
from dotenv import load_dotenv
from faker import Faker
from pymongo import MongoClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed a MongoDB collection with mock restaurant catalog data.")
    parser.add_argument("--count", type=int, default=1000, help="Number of documents to insert (default: 1000).")
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop the target collection before inserting the generated documents.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate the documents but do not insert them. Useful for validation.",
    )
    return parser.parse_args()


def load_settings() -> tuple[str, str, str]:
    load_dotenv()

    mongo_uri = os.getenv("MONGODB_URI")
    db_name = os.getenv("DB_NAME")
    collection_name = os.getenv("COLLECTION_NAME")

    missing = [name for name, value in [("MONGODB_URI", mongo_uri), ("DB_NAME", db_name), ("COLLECTION_NAME", collection_name)] if not value]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    return mongo_uri, db_name, collection_name


def random_catalog_id(country_code: str, area_type: str) -> str:
    suffix = "".join(random.choices(string.digits, k=6))
    return f"{country_code}-{area_type}-{suffix}"


def random_title(faker: Faker) -> str:
    base = random.choice(["McOfertas", "McCombos", "Menu Ejecutivo", "Desayuno Express", "Momentos Compartidos"])
    descriptor = random.choice(["Snacks", "Deluxe", "Signature", "Family", "Flex"])
    period = random.choice(["(Desayuno)", "(Almuerzo)", "(Cena)", "(24h)", "(Promo)"])
    return f"{base} {descriptor} {period}"


def random_image_url(folder: str) -> str:
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=7))
    date_tag = datetime.utcnow().strftime("%d%m%Y")
    return f"https://d2umxhib5z7frz.cloudfront.net/Peru/{folder}_{code}_{date_tag}.png"


def random_availability() -> list[dict]:
    days = ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"]
    availability = []
    for day in days:
        start_hour = random.randint(5, 10)
        start_minute = random.choice(["00", "15", "30", "45"])
        duration_hours = random.randint(3, 8)
        end_hour = min(start_hour + duration_hours, 23)
        end_minute = random.choice(["00", "15", "30", "45"])
        availability.append(
            {
                "dayOfWeek": day,
                "timePeriods": [
                    {
                        "startTime": f"{start_hour:02d}:{start_minute}",
                        "endTime": f"{end_hour:02d}:{end_minute}",
                    }
                ],
            }
        )
    return availability


def format_price(amount: float) -> str:
    return f"S/{amount:0.2f}".replace(".", ",")


def random_sizes() -> list[dict]:
    sizes = [
        {"id": "LARGE", "code": "".join(random.choices(string.digits, k=5))},
        {"id": "MEDIUM", "code": "".join(random.choices(string.digits, k=5))},
        {"id": "SMALL", "code": "".join(random.choices(string.digits, k=5))},
        {"id": "NONE", "code": "".join(random.choices(string.digits, k=5))},
    ]
    return random.sample(sizes, k=random.randint(2, len(sizes)))


def random_product(faker: Faker) -> dict:
    product_templates = [
        ("Hamburguesa con Queso", "Hamburguesa de res con queso cheddar y pepinillos."),
        ("Sándwich de Pollo con Queso", "Hamburguesa de pollo crujiente con lechuga y mayonesa."),
        ("Nuggets x4", "4 Chicken McNuggets con salsa a elección."),
        ("Papas Regulares", "Papas fritas crujientes en tamaño regular."),
        ("Pie de Manzana", "Pastel de manzana caliente con canela."),
        ("Cafe Pasado", "Café americano de 14 oz, molido y filtrado al instante."),
        ("McFlurry Oreo", "Helado de vainilla con trozos de galleta Oreo."),
        ("Sundae de Caramelo", "Helado suave con topping de caramelo."),
        ("McWrap Premium", "Wrap de pollo con vegetales frescos."),
        ("Ensalada César", "Ensalada con pollo a la parrilla, parmesano y aderezo César."),
    ]
    name, base_description = random.choice(product_templates)
    description = f"{base_description} {faker.sentence(nb_words=10)}"
    amount = round(random.uniform(2.5, 25.0), 2)
    areas = ["MOP", "AUT", "CURB", "EALM"]
    product = {
        "id": "".join(random.choices(string.digits, k=5)),
        "name": name,
        "description": description,
        "imageUrl": random_image_url("DLV"),
        "price": {
            "amount": amount,
            "formatted": format_price(amount),
        },
        "available": random.choice([True, False]),
        "areas": random.sample(areas, k=random.randint(1, len(areas))),
        "combo": random.choice([True, False]),
        "_id": ObjectId(),
    }
    if random.random() < 0.6:
        product["sizes"] = random_sizes()
    if random.random() < 0.4:
        product["isPromoFlex"] = random.choice([True, False])
    return product


def random_catalog(faker: Faker) -> dict:
    country_options = [
        ("62f4a5554ce4bb3644827e11", "PE"),
        (str(ObjectId()), "CL"),
        (str(ObjectId()), "CO"),
        (str(ObjectId()), "MX"),
    ]
    country_id, country_code = random.choice(country_options)
    area_codes = ["MOP", "AUT", "CURB", "EALM"]
    area_types = ["PICKUP", "DELIVERY", "DRIVE_THRU", "EAT_IN"]
    area_code = random.choice(area_codes)
    area_type = random.choice(area_types)

    catalog_id = random_catalog_id(country_code, area_type)

    created_at = faker.date_time_between(start_date="-2y", end_date="now", tzinfo=timezone.utc)
    updated_at = created_at + timedelta(days=random.randint(0, 120), hours=random.randint(0, 12))

    restaurant_name = faker.city().upper()
    doc = {
        "id": catalog_id,
        "title": random_title(faker),
        "imageUrl": random_image_url("category"),
        "countryId": country_id,
        "countryCode": country_code,
        "areaCode": area_code,
        "areaType": area_type,
        "restaurant": ObjectId(),
        "restaurantCode": "".join(random.choices(string.ascii_uppercase, k=3)),
        "restaurantName": restaurant_name,
        "availability": random_availability(),
        "products": [random_product(faker) for _ in range(random.randint(3, 8))],
        "createdAt": created_at,
        "updatedAt": updated_at,
        "__v": 0,
    }
    return doc


def create_faker(locales: Iterable[str]) -> Faker:
    for locale in locales:
        try:
            return Faker(locale)
        except AttributeError:
            continue
    raise RuntimeError(f"None of the requested Faker locales are available: {', '.join(locales)}")


def main() -> None:
    args = parse_args()
    mongo_uri, db_name, collection_name = load_settings()

    requested_locale = "es_ES"
    locale_preferences = []
    if requested_locale:
        locale_preferences.append(requested_locale)
    locale_preferences.extend(["es_ES", "es_MX", "es_US", "en_US"])
    unique_locales = []
    for loc in locale_preferences:
        if loc not in unique_locales:
            unique_locales.append(loc)

    faker = create_faker(unique_locales)
    Faker.seed(random.randint(0, 999999))

    documents = [random_catalog(faker) for _ in range(args.count)]

    if args.dry_run:
        print(f"Generated {len(documents)} documents (dry run, nothing inserted).")
        return

    client = MongoClient(mongo_uri)
    try:
        collection = client[db_name][collection_name]
        if args.drop:
            collection.drop()

        result = collection.insert_many(documents)
        print(f"Inserted {len(result.inserted_ids)} documents into {db_name}.{collection_name}.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
