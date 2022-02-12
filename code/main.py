from flask import Flask, render_template, request
from sqlitedict import SqliteDict
import os
import datetime
import random
import logging


from typing import List, Optional
from pydantic import BaseModel

data_folder = '/data'
if not os.path.exists(data_folder):
    data_folder = '../data'

app = Flask(__name__, static_url_path='/static', static_folder=data_folder, template_folder='')
logger = app.logger
logger.setLevel(logging.DEBUG)

codes_table = SqliteDict(os.path.join(data_folder, 'main.db'), tablename="codes", autocommit=True)
main_table = SqliteDict(os.path.join(data_folder, 'main.db'), tablename="main", autocommit=True)
players_table = SqliteDict(os.path.join(data_folder, 'progress.db'), tablename="players", autocommit=True)
animals_table = SqliteDict(os.path.join(data_folder, 'progress.db'), tablename="animals", autocommit=True)
active_animals_table = SqliteDict(os.path.join(data_folder, 'progress.db'), tablename="active_animals", autocommit=True)
spawned_animals_table = SqliteDict(os.path.join(data_folder, 'progress.db'), tablename="spawned_animals", autocommit=True)
powerups_table = SqliteDict(os.path.join(data_folder, 'progress.db'), tablename="powerups", autocommit=True)

pokemons_table = SqliteDict(os.path.join(data_folder, 'pokemons.db'), tablename="pokemons", autocommit=False)

FRUIT_SLUGS = ['watermelon', 'carrot', 'apple', 'sandvich']


class Animal(BaseModel):
    active = False
    spawned = False
    spawns = True
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
    location: Optional[str]  # Slug of the point where this animal is currently located
    target: Optional[str]  # Slug of the point where this animal is going
    target_time: Optional[datetime.datetime]  # When this animal is going to reach its target
    timeout: Optional[datetime.datetime]  # When this animal is going to be removed from the game


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
    gift = False


class Powerup(BaseModel):
    name: str
    slug: str
    duration: int
    active: bool
    available: bool
    cooldown: int
    start_time: datetime.datetime


powerups_table['super_fruits'] = Powerup(
    slug='super_fruits',
    name='Kaikki on superhedelmiä',
    duration=45,
    cooldown=60 * 5,
    active=False,
    available=True,
    start_time=datetime.datetime.now() - datetime.timedelta(days=1),
)

# Load pokemons
for animal_slug in list(animals_table.keys()):
    del animals_table[animal_slug]

for animal_slug in list(active_animals_table.keys()):
    del active_animals_table[animal_slug]

for animal_slug in list(spawned_animals_table.keys()):
    del spawned_animals_table[animal_slug]

for pokemon_name, pokemon in pokemons_table.items():
    front_default = os.path.join(data_folder, pokemon_name, 'animated', 'front_default.gif')
    if not os.path.exists(front_default):
        logger.info("Skipping pokemon %s, no images", pokemon_name)
        continue
    
    animals_table[pokemon_name] = Animal(
        slug=pokemon_name,
        name=pokemon_name.capitalize(),
        fruit_slug='watermelon',
        fruit=0,
        eating_speed=random.randint(5, 9),
        experience=0,
        level=0,
        start_eating=datetime.datetime.now(),
        last_source=None,
        evolution=None,
        location=None,
        target=None,
        target_time=None,
    )
    logger.info("Loaded pokemon %s", pokemon_name)
    
for pokemon_name, pokemon in pokemons_table.items():
    if 'evolution' not in pokemon:
        continue
    if pokemon['evolution'] not in animals_table:
        continue
    next_evolution = animals_table[pokemon['evolution']]
    next_evolution.spawns = False
    animals_table[pokemon_name] = next_evolution

FRUIT_TIMEOUT = 60
ANIMAL_TIMEOUT = 2 * 60
ANIMAL_CLOSE_TIMEOUT = 30

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


def table_setter(table, table_key, key, value):
    table_row = table[table_key]
    table_row[key] = value
    table[table_key] = table_row


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
    point.gift = False
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


def active_powerups():
    return {key: value for key, value in powerups_table.items() if value.active}


def handle_fruit_collected(point, timeout=False):
    handled = False
    if timeout:
        logger.info("Fruit timeout: %s at %s", point.fruit, point.barcode)
        point.fruit = None
        # Respawn faster after timeout
        point.fruit_death = datetime.datetime.now() - datetime.timedelta(seconds=60)
        handled = True

    if not handled:
        for key, powerup in powerups_table.items():
            if powerup.slug == point.fruit:
                powerup.active = True
                powerup.start_time = datetime.datetime.now()
                powerups_table[key] = powerup
                point.fruit = None
                point.fruit_death = datetime.datetime.now()
                handled = True
                logger.info("Powerup collected: %s at %s", powerup.slug, point.barcode)

    if not handled:
        for key, animal in active_animals_table.items():
            if not animal.active:
                continue
            if animal.fruit_slug == point.fruit:
                logger.info("Fruit collected: %s at %s", point.fruit, point.barcode)
                if animal.fruit == 0:
                    animal.start_eating = datetime.datetime.now()
                animal.fruit += 1
                if point.super_fruit or 'super_fruits' in active_powerups():
                    animal.fruit += 4
                animal.last_source = point.barcode
                animal.timeout = datetime.datetime.now() + datetime.timedelta(seconds=ANIMAL_TIMEOUT)
                active_animals_table[animal.slug] = animal
                point.fruit = None
                point.fruit_death = datetime.datetime.now()
                handled = True
        else:
            logger.warning("Fruit %s not found in any table", point.fruit)
            point.fruit = None
    
    codes_table[point.barcode] = point

    for point in codes_table.values():
        if point.fruit:
            break
    else:
        logger.info("All fruits collected")
        point = random.choice(list(codes_table.values()))
        respawn_fruit(point)


def respawn_fruit(point):
    powerups = []
    for powerup_slug, powerup in powerups_table.items():
        if powerup.active or not powerup.available:
            continue
        if powerup.start_time + datetime.timedelta(seconds=powerup.cooldown) > datetime.datetime.now():
            continue
        for _point in codes_table.values():
            if _point.fruit == powerup_slug:
                break
        else:
            powerups.append(powerup)

    gift_exists = False
    for key, _point in codes_table.items():
        if _point.fruit and _point.gift:
            gift_exists = True
            break

    spawn_type = "fruit"
    point.gift = not gift_exists
    if not gift_exists:
        if random.randint(0, 100) < 50:
            if len(powerups) > 0:
                spawn_type = "powerup"

    point.super_fruit = False

    if spawn_type == "powerup":
        powerup = random.choice(powerups)
        logger.info("Powerup %s spawned", powerup.slug)
        point.fruit = powerup.slug
        point.fruit_timeout = datetime.datetime.now() + datetime.timedelta(seconds=FRUIT_TIMEOUT)
    else:
        fruit_slugs = list(set([animal.fruit_slug for animal in active_animals_table.values()]))
        if len(fruit_slugs) == 0:
            fruit_slugs = FRUIT_SLUGS
        point.fruit = random.choice(fruit_slugs)
        point.super_fruit = random.randint(0, 100) < 10
        point.fruit_timeout = datetime.datetime.now() + datetime.timedelta(seconds=FRUIT_TIMEOUT)
        logger.info("Fruit respawned at code %s: %s", point.barcode, point.fruit)
    codes_table[point.barcode] = point


def handle_animal_spawns(to_spawn):
    logger.info("Spawning %s animals", to_spawn)
    available_animals = [
        animal for animal in animals_table.values()
        if animal.slug not in active_animals_table and animal.slug not in spawned_animals_table
    ]
    to_spawn = random.choices(available_animals, k=to_spawn)
    for animal in to_spawn:
        animal.spawned = True
        animal.location = random.choice(list(codes_table.keys()))
        animal.target = random.choice([point for point in codes_table.keys() if point != animal.location])
        animal.target_time = datetime.datetime.now() + datetime.timedelta(seconds=random.randint(10, 30))
        animal.timeout = datetime.datetime.now() + datetime.timedelta(seconds=ANIMAL_TIMEOUT)
        animals_table[animal.slug] = animal
        spawned_animals_table[animal.slug] = animal
        logger.info("Animal spawned: %s", animal.slug)


def handle_spawned_animal(animal):
    if animal.timeout and animal.timeout < datetime.datetime.now():
        logger.info("Animal %s timeout", animal.slug)
        animal.timeout = None
        animal.spawned = False
        spawned_animals_table.pop(animal.slug)
        return

    if animal.target and animal.target_time:
        if animal.target_time < datetime.datetime.now():
            animal.location = animal.target
            animal.target = random.choice([point for point in codes_table.keys() if point != animal.location])
            animal.target_time = datetime.datetime.now() + datetime.timedelta(seconds=random.randint(10, 30))
            spawned_animals_table[animal.slug] = animal


def handle_animal_eating(animal):
    if animal.timeout and animal.timeout < datetime.datetime.now():
        logger.info("Animal %s timeout", animal.slug)
        animal.timeout = None
        animal.active = False
        active_animals_table.pop(animal.slug)
        return

    if not animal.fruit or animal.fruit < 1:
        animal.fruit = 0
    elif animal.start_eating < (datetime.datetime.now() - datetime.timedelta(seconds=animal.eating_speed)):
        animal.fruit = animal.fruit - 1
        animal.timeout = datetime.datetime.now() + datetime.timedelta(seconds=ANIMAL_TIMEOUT)
        animal.start_eating = datetime.datetime.now()
        logger.info("%s ate a %s: %s left", animal.name, animal.fruit_slug, animal.fruit)
        animal.experience += 1
    animal.level = int(animal.experience / 2)
    if animal.level >= 3 and animal.evolution:
        animal.active = False
        fruit_overflow = animal.fruit
        animal.fruit = 0
        animal.spawns = False
        active_animals_table[animal.slug] = animal
        animal = active_animals_table[animal.evolution]
        animal.active = True
        animal.fruit = fruit_overflow
    active_animals_table[animal.slug] = animal


def handle_animal_collected(animal):
    animal.active = True
    animal.fruit = 0
    animal.spawned = False
    animal.timeout = datetime.datetime.now() + datetime.timedelta(seconds=ANIMAL_TIMEOUT)
    fruits_available = FRUIT_SLUGS
    # Check active animals and pick one fruit not used yet for this animal
    for active_animal in active_animals_table.values():
        if active_animal.active and active_animal.fruit_slug in fruits_available:
            fruits_available.remove(active_animal.fruit_slug)
    animal.fruit_slug = random.choice(fruits_available)
    active_animals_table[animal.slug] = animal
    if animal.slug in spawned_animals_table:
        del spawned_animals_table[animal.slug]
    logger.info("%s collected: %s", animal.name, animal.fruit_slug)


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

    for key, powerup in powerups_table.items():
        if powerup.active and powerup.start_time + datetime.timedelta(seconds=powerup.duration) < datetime.datetime.now():
            powerup.active = False
            powerups_table[key] = powerup
            logger.info("Powerup %s expired", powerup.slug)

    for key, animal in active_animals_table.items():
        handle_animal_eating(animal)

    for key, animal in spawned_animals_table.items():
        handle_spawned_animal(animal)

    animal_to_spawn = 4 - len(spawned_animals_table) - len(active_animals_table)
    if animal_to_spawn > 0:
        handle_animal_spawns(animal_to_spawn)


    dead_players = []
    for key, player in players_table.items():
        if not player.last_seen or (player.last_seen < datetime.datetime.now() - datetime.timedelta(minutes=10)):
            dead_players.append(key)

    for key in dead_players:
        del players_table[key]

    codes = table_to_dict(codes_table)
    for key in codes:
        codes[key]["close_to_timeout"] = codes[key]["fruit_timeout"] < (datetime.datetime.now() + datetime.timedelta(seconds=15))

    spawned_animals = table_to_dict(spawned_animals_table)
    for key in spawned_animals:
        if spawned_animals[key]["timeout"]:
            spawned_animals[key]["close_to_timeout"] = spawned_animals[key]["timeout"] < (datetime.datetime.now() + datetime.timedelta(seconds=ANIMAL_CLOSE_TIMEOUT))
        spawned_animals[key]["seconds_to_target"] = (spawned_animals[key]["target_time"] - datetime.datetime.now()).seconds

    active_animals = table_to_dict(active_animals_table)
    for key in active_animals:
        if active_animals[key]["timeout"]:
            active_animals[key]["close_to_timeout"] = active_animals[key]["timeout"] < (datetime.datetime.now() + datetime.timedelta(seconds=ANIMAL_CLOSE_TIMEOUT))

    return {
        "codes": codes,
        "players": table_to_dict(players_table),
        "powerups": table_to_dict(powerups_table),
        "animals": active_animals,
        "spawned_animals": spawned_animals
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
        elif point.fruit == 'sandvich':
            ret += 'leivän!'
        elif point.fruit == 'super_fruits':
            ret += 'pullon! Kaikki hedelmät on isoja!'
        else:
            ret += point.fruit + '!'

    if point.fruit:
        handle_fruit_collected(point)

    for key, animal in spawned_animals_table.items():
        if animal.target == point.barcode:
            handle_animal_collected(animal)
            ret += ' sait kiinni pokemonin ' + animal.name + '!'

    return ret
