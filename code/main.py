from flask import Flask, render_template, request
from sqlitedict import SqliteDict
import os
import datetime
import random

from typing import List, Optional
from pydantic import BaseModel

data_folder = '/data'
if not os.path.exists(data_folder):
    data_folder = '../data'

app = Flask(__name__, static_url_path='/static', static_folder=data_folder, template_folder='')
logger = app.logger

codes_table = SqliteDict(os.path.join(data_folder, 'main.db'), tablename="codes", autocommit=True)
main_table = SqliteDict(os.path.join(data_folder, 'main.db'), tablename="main", autocommit=True)
players_table = SqliteDict(os.path.join(data_folder, 'progress.db'), tablename="players", autocommit=True)
animals_table = SqliteDict(os.path.join(data_folder, 'progress.db'), tablename="animals", autocommit=True)


class Animal(BaseModel):
    active: bool
    slug: str
    name = 'Nimi'
    fruit_slug: str
    fruit = 1
    eating_speed = 8
    experience = 0
    level = 0
    start_eating: datetime.datetime
    last_source: Optional[str]  # Where this animal last received a fruit from
    evolution: Optional[str]  # Slug of the animal that this animal evolves into


class Player(BaseModel):
    name = ''
    ip_address: str
    last_seen: datetime.datetime
    history: List[str]


class Point(BaseModel):
    barcode: str
    x: int
    y: int
    name: Optional[str]
    fruit: Optional[str]
    fruit_death: Optional[datetime.datetime]
    super_fruit = False
    fruit_timeout: Optional[datetime.datetime]
    close_to_timeout = False


# if 'mouse' not in animals_table or init_tables:
animals_table['mouse'] = Animal(**{
    "active": False,
    "name": "Hiiri",
    "slug": "mouse",
    "image": "mouse.png",
    "fruit_slug": "apple",
    "fruit": 1,
    "eating_speed": 8,  # seconds
    "start_eating": datetime.datetime.now(),
    "experience": 0,
    "level": 0,
})

# if 'bunny' not in animals_table or init_tables:
animals_table['bunny'] = Animal(**{
    "active": False,
    "name": "Pupu",
    "slug": "bunny",
    "image": "bunny.png",
    "fruit_slug": "carrot",
    "fruit": 1,
    "eating_speed": 10,  # seconds
    "start_eating": datetime.datetime.now(),
    "experience": 0,
    "level": 0,
})

animals_table['pikachu'] = Animal(**{
    "active": True,
    "name": "Pupu",
    "slug": "pikachu",
    "image": "pikachu.png",
    "fruit_slug": "watermelon",
    "fruit": 1,
    "eating_speed": 1,  # seconds
    "start_eating": datetime.datetime.now(),
    "experience": 0,
    "level": 0,
    "evolution": "raichu",
})

animals_table['raichu'] = Animal(**{
    "active": False,
    "name": "Raichu",
    "slug": "raichu",
    "image": "raichu.png",
    "fruit_slug": "watermelon",
    "fruit": 1,
    "eating_speed": 15,  # seconds
    "start_eating": datetime.datetime.now(),
    "experience": 0,
    "level": 0,
})

FRUIT_TIMEOUT = 60

def _init_row(barcode=''):
    return Point(**{
        'barcode': barcode,
        'x': 0.1,
        'y': 0.1,
        'name': None,
        'fruit': None,
        'fruit_death': datetime.datetime.now() - datetime.timedelta(days=1),
        "super_fruit": False,
        'fruit_timeout': datetime.datetime.now() + datetime.timedelta(seconds=FRUIT_TIMEOUT),
    })


INITIAL_CODES = [
    'http://koodi-1',
    'http://koodi-2',
    'http://koodi-3',
    'http://koodi-4',
    'http://koodi-5',
    'http://koodi-6',
    'http://koodi-7',
    'http://koodi-8',
    'http://koodi-9',
    'http://koodi-10',
    'http://koodi-11',
    'http://koodi-12',
]
for initial_code in INITIAL_CODES:
    if initial_code not in codes_table:
        codes_table[initial_code] = _init_row(initial_code)


for key, point in codes_table.items():
    point.fruit_death = datetime.datetime.now() - datetime.timedelta(days=1)
    codes_table[key] = point


@app.route("/")
def hello_world():
    return render_template("index.html", title = 'App')


@app.route("/api/add", methods=['POST'])
def add_barcode():
    barcode = request.json.get('barcode')
    if not barcode:
        return 'No barcode provided'
    if 'koodi' not in barcode:
        return 'No koodi provided'
    row = _init_row()
    row.barcode = barcode
    codes_table[barcode] = row
    return 'ok'


@app.route("/api/modify", methods=['POST'])
def modify_barcode():
    barcode = request.json.get('barcode')
    if not barcode:
        return 'No barcode provided'
    x = request.json.get('x')
    y = request.json.get('y')
    name = request.json.get('name')
    row = codes_table.get(barcode)
    if not row:
        return 'error'
    row.x = x
    row.y = y
    if name:
        row.name = name
    codes_table[barcode] = row
    return 'ok'


def distance(x1, y1, x2, y2):
    return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5


def handle_fruit_collected(point, timeout=False):
    for key, animal in animals_table.items():
        if not animal.active:
            continue
        if animal.fruit_slug == point.fruit:
            if timeout:
                logger.info("Fruit timeout: %s at %s", point.fruit, point.barcode)
            else:
                logger.info("Fruit collected: %s at %s", point.fruit, point.barcode)
                if animal.fruit == 0:
                    animal.start_eating = datetime.datetime.now()
                animal.fruit += 1
                if point.super_fruit:
                    animal.fruit += 4
                animal.last_source = point.barcode
                animals_table[animal.slug] = animal
            point.fruit = None
            point.fruit_death = datetime.datetime.now()
            if timeout:
                # Respawn faster after timeout
                point.fruit_death = datetime.datetime.now() - datetime.timedelta(seconds=60)
            codes_table[point.barcode] = point

            for point in codes_table.values():
                if point.fruit:
                    break
            else:
                logger.info("All fruits collected")
                point = random.choice(list(codes_table.values()))
                respawn_fruit(point)
            break
    else:
        logger.warning("Fruit %s not found in animals table", point.fruit)
        point.fruit = None
        codes_table[point.barcode] = point

def respawn_fruit(point):
    fruit_slugs = list(set([animal.fruit_slug for animal in animals_table.values() if animal.active]))
    point.fruit = random.choice(fruit_slugs)
    point.super_fruit = random.randint(0, 100) < 10
    point.fruit_timeout = datetime.datetime.now() + datetime.timedelta(seconds=FRUIT_TIMEOUT)
    logger.info("Fruit respawned at code %s: %s", point.barcode, point.fruit)
    codes_table[point.barcode] = point


def handle_animal_eating(animal):
    if not animal.fruit or animal.fruit < 1:
        animal.fruit = 0
    elif animal.start_eating < (datetime.datetime.now() - datetime.timedelta(seconds=animal.eating_speed)):
        animal.fruit = animal.fruit - 1
        animal.start_eating = datetime.datetime.now()
        logger.info("%s ate a %s: %s left", animal.name, animal.fruit_slug, animal.fruit)
        animal.experience += 1
    animal.level = int(animal.experience / 5)
    if animal.level >= 3 and animal.evolution:
        animal.active = False
        animals_table[animal.slug] = animal
        animal = animals_table[animal.evolution]
        animal.active = True
    animals_table[animal.slug] = animal


def table_to_dict(_dict):
    return {key: dict(value) for key, value in _dict.items()}


@app.route("/api/tick")
def game_tick():
    for key, point in codes_table.items():
        if point.fruit and point.fruit_timeout < datetime.datetime.now():
            handle_fruit_collected(point, timeout=True)
        if point.fruit:
            continue
        if not point.fruit_death or point.fruit_death < (datetime.datetime.now() - datetime.timedelta(seconds=90)):
            respawn_fruit(point)

    for key, animal in animals_table.items():
        handle_animal_eating(animal)

    dead_players = []
    for key, player in players_table.items():
        if not player.last_seen or (player.last_seen < datetime.datetime.now() - datetime.timedelta(minutes=10)):
            dead_players.append(key)

    for key in dead_players:
        del players_table[key]

    codes = table_to_dict(codes_table)
    for key in codes:
        codes[key]["close_to_timeout"] = codes[key]["fruit_timeout"] < (datetime.datetime.now() + datetime.timedelta(seconds=15))

    animals = {key: value for key, value in table_to_dict(animals_table).items() if value["active"]}

    return {
        "codes": codes,
        "players": table_to_dict(players_table),
        "animals": animals,
    }


@app.route("/api/mark", methods=['POST'])
def mark_barcodes():
    ip_address = request.remote_addr
    barcode = request.json.get("barcode")
    if not barcode:
        return 'No barcode provided'
    if barcode not in codes_table:
        return 'Barcode not found'
    player = players_table.get(ip_address)
    if not player:
        player = Player(**{
            "history": [],
            "ip_address": ip_address,
            "last_seen": datetime.datetime.now(),
        })

    player.history.append(barcode)
    player.history = player.history[-4:]
    players_table[ip_address] = player

    point = codes_table[barcode]

    logger.info("player visited %s", barcode)
    ret = 'Ruokaa ei löytynyt'
    if point.fruit:
        ret = 'Hyvä, löysit '
        if point.super_fruit:
            ret += 'ison '
        if point.fruit == 'watermelon':
            ret += 'vesimelonin!'
        elif point.fruit == 'apple':
            ret += 'omenan!'
        elif point.fruit == 'carrot':
            ret += 'porkkanan!'

    if point.fruit:
        handle_fruit_collected(point)

    return ret
