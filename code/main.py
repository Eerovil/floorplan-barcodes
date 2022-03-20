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
shelved_animals_table = SqliteDict(os.path.join(data_folder, 'progress.db'), tablename="shelved_animals", autocommit=True)
powerups_table = SqliteDict(os.path.join(data_folder, 'progress.db'), tablename="powerups", autocommit=True)
points_by_distance_table = SqliteDict(os.path.join(data_folder, 'progress.db'), tablename="points_by_distance_table", autocommit=True)

maps_table = SqliteDict(os.path.join(data_folder, 'main.db'), tablename="maps", autocommit=True)

# pokemons_table = SqliteDict(os.path.join(data_folder, 'pokemons.db'), tablename="pokemons", autocommit=False)
pokemons_table = {}

img_animals_table = SqliteDict(os.path.join(data_folder, 'img_animals.db'), tablename="img_animals", autocommit=False)

FRUIT_SLUGS = ['watermelon', 'carrot', 'apple', 'sandvich']

main_table['last_tick'] = datetime.datetime.now()

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
    target: Optional[str]  # Slug of the point or map point where this animal is going
    real_target: Optional[str]  # Slug of the point where this animal is going
    target_time: Optional[datetime.datetime]  # When this animal is going to reach its target
    timeout: Optional[datetime.datetime]  # When this animal is going to be removed from the game
    shiny = False
    filled = False


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
    connections = []


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

for animal_slug in list(shelved_animals_table.keys()):
    del shelved_animals_table[animal_slug]

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
        eating_speed=3,
        experience=0,
        level=0,
        start_eating=datetime.datetime.now(),
        last_source=None,
        evolution=pokemon.get('evolution'),
        location=None,
        target=None,
        target_time=None,
    )
    logger.info("Loaded pokemon %s, evolution: %s", pokemon_name, pokemon.get('evolution'))
    
for pokemon_name, pokemon in pokemons_table.items():
    if 'evolution' not in pokemon:
        continue
    if pokemon['evolution'] not in animals_table:
        continue
    next_evolution = animals_table[pokemon['evolution']]
    next_evolution.spawns = False
    animals_table[pokemon['evolution']] = next_evolution


for img_animal_slug, img_animal in img_animals_table.items():
    front_default = os.path.join(data_folder, img_animal_slug)
    if not os.path.exists(front_default):
        logger.info("Skipping img_animal %s, no images", img_animal_slug)
        continue
    
    animals_table[img_animal_slug] = Animal(
        slug=img_animal_slug,
        name=img_animal_slug.replace('img_animals/', '').capitalize().replace('-', ' ').replace('_', ' ').split('.')[0],
        fruit_slug='watermelon',
        fruit=0,
        eating_speed=3,
        experience=0,
        level=0,
        start_eating=datetime.datetime.now(),
        last_source=None,
        evolution=None,
        location=None,
        target=None,
        target_time=None,
    )
    logger.info("Loaded img_animal %s", animals_table[img_animal_slug].name)
    

FRUIT_TIMEOUT = 60
ANIMAL_TIMEOUT = 4 * 60
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
ANIMAL_SKIP_CODES = ['http://koodi-10', 'http://koodi-11']
for initial_code in INITIAL_CODES:
    if initial_code not in codes_table:
        codes_table[initial_code] = _init_row(initial_code)


point_names = {
    'http://koodi-1': 'Eteisessä',
    'http://koodi-2': 'Kuivausrummussa',
    'http://koodi-3': 'Pelihuoneessa',
    'http://koodi-4': 'Jääkaapissa',
    'http://koodi-5': 'Einarin huoneessa',
    'http://koodi-6': 'Terassin ovella',
    'http://koodi-7': 'Työhuoneessa',
    'http://koodi-8': 'Verstaan ovella',
    'http://koodi-9': 'Makuuhuoneessa',
    'http://koodi-10': 'Telkkarin luona',
    'http://koodi-11': 'Sohvan takana',
    'http://koodi-12': 'Valtterin huoneessa',
}


def get_point(barcode):
    point = codes_table.get(barcode)
    if not point:
        point = maps_table.get(barcode)
    return point


for key in list(codes_table.keys()):
    if 'map-' in key:
        del codes_table[key]


for key in list(maps_table.keys()):
    if 'map-' not in key:
        del maps_table[key]


for key, point in codes_table.items():
    point.fruit_death = datetime.datetime.now() - datetime.timedelta(days=1)
    point.fruit_timeout = datetime.datetime.now()
    point.connections = getattr(point, 'connections', [])
    point.gift = False
    missing_connections = set()
    for connection in point.connections:
        if connection == key:
            continue
        connected_point = get_point(connection)
        if not connected_point:
            missing_connections.add(connection)
            continue
        if key not in connected_point.connections:
            connected_point.connections.append(key)
            if connection in codes_table:
                codes_table[connection] = connected_point
            else:
                maps_table[connection] = connected_point
    for connection in missing_connections:
        point.connections.remove(connection)
    codes_table[key] = point


for key, point in maps_table.items():
    point.connections = getattr(point, 'connections', [])
    missing_connections = set()
    for connection in point.connections:
        if connection == key:
            continue
        connected_point = get_point(connection)
        if not connected_point:
            missing_connections.add(connection)
            continue
        if key not in connected_point.connections:
            connected_point.connections.append(key)
            if connection in codes_table:
                codes_table[connection] = connected_point
            else:
                maps_table[connection] = connected_point

    for connection in missing_connections:
        point.connections.remove(connection)
    maps_table[key] = point


logger.info("codes_table: %s", len(codes_table))
logger.info("maps_table: %s", len(maps_table))


@app.route("/")
def hello_world():
    return render_template("index.html", title = 'App')


@app.route("/tv")
def tv_html():
    return render_template("tv.html", title = 'App')


@app.route("/client")
def client_html():
    return render_template("client.html", title = 'App')


@app.route("/api/add", methods=['POST'])
def add_barcode():
    barcode = request.json.get('barcode')
    if not barcode:
        return 'No barcode provided'
    is_map = False
    if 'map-' in barcode:
        is_map = True
    elif 'koodi' not in barcode:
        return 'No koodi provided'
    row = _init_row()
    row.barcode = barcode
    if is_map:
        row.x = request.json.get('x', 0.1)
        row.y = request.json.get('y', 0.1)
        maps_table[barcode] = row
    else:
        codes_table[barcode] = row
    return 'ok'


@app.route("/api/connect", methods=['POST'])
def connect_barcodes():
    barcode1 = request.json.get('barcode1')
    barcode2 = request.json.get('barcode2')
    if not barcode1 or not barcode2:
        return 'No barcode provided'
    
    # handle barcode1
    barcode1_is_map = False
    if barcode1 not in codes_table:
        barcode1_is_map = True
        if barcode1 not in maps_table:
            return 'No barcode1 found anywhere'

    barcode2_is_map = False
    if barcode2 not in codes_table:
        barcode2_is_map = True
        if barcode2 not in maps_table:
            return 'No barcode2 found anywhere'

    if barcode1_is_map:
        table = maps_table
    else:
        table = codes_table

    code1 = table[barcode1]
    code1.connections = getattr(code1, 'connections', None) or []

    to_remove = False
    if barcode2 in code1.connections:
        to_remove = True
        code1.connections = [x for x in code1.connections if x != barcode2]
    else:
        code1.connections.append(barcode2)
        code1.connections = [_code for _code in set(code1.connections) if _code != barcode1]
    table[barcode1] = code1

    if barcode2_is_map:
        table = maps_table
    else:
        table = codes_table

    code2 = table[barcode2]
    code2.connections = getattr(code2, 'connections', None) or []

    if to_remove:
        code2.connections = [x for x in code2.connections if x != barcode1]
    else:
        code2.connections.append(barcode1)
        code2.connections = [_code for _code in set(code2.connections) if _code != barcode2]
    table[barcode2] = code2
    
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
    is_map = False
    if not row:
        row = maps_table.get(barcode)
        is_map = True
        if not row:
            return 'error'
    row.x = x
    row.y = y
    if name:
        row.name = name
    if is_map:
        maps_table[barcode] = row
    else:
        codes_table[barcode] = row
    return 'ok (is_map: %s)' % is_map


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
                    animal.fruit += 2
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
    point.gift = not gift_exists and random.randint(0, 100) < 50
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
        if len(fruit_slugs) > 0:
            point.fruit = random.choice(fruit_slugs)
            point.super_fruit = random.randint(0, 100) < 10
            point.fruit_timeout = datetime.datetime.now() + datetime.timedelta(seconds=FRUIT_TIMEOUT)
            logger.info("Fruit respawned at code %s: %s", point.barcode, point.fruit)
    codes_table[point.barcode] = point


def barcode_distance(barcode1, barcode2):
    point1 = get_point(barcode1)
    point2 = get_point(barcode2)
    if not point1 or not point2:
        return 0
    return distance(point1.x, point1.y, point2.x, point2.y)


def find_next_in_path(barcode1, barcode2):
    point1 = get_point(barcode1)
    
    def _check_path(_barcode, parent, checked_points=None):
        checked_points = set(checked_points or set())
        if _barcode in checked_points:
            return 0
        point = get_point(_barcode)
        checked_points.add(_barcode)
        # logger.info("Checking path %s with connections %s", _barcode, point.connections)
        for connection in getattr(point, 'connections', []):
            if connection == parent:
                continue
            if connection == barcode2:
                return barcode_distance(_barcode, barcode2)
            _distance = _check_path(connection, parent=point.barcode, checked_points=checked_points)
            if _distance > 0:
                return _distance + barcode_distance(_barcode, connection)
        return 0

    best_connection_distance = 9999
    best_connection = None
    for main_connection in getattr(point1, 'connections', []):
        if main_connection == barcode2:
            return main_connection, 0
        _distance = _check_path(main_connection, parent=point1.barcode)
        if _distance > 0:
            _distance += barcode_distance(barcode1, main_connection)
        if _distance > 0 and _distance < best_connection_distance:
            best_connection = main_connection
            best_connection_distance = _distance

    if best_connection:
        return best_connection, best_connection_distance
    
    logger.warning("No path found from %s to %s", barcode1, barcode2)
    _random_connetions = [_conn for _conn in getattr(point1, 'connections', []) if _conn != barcode1]
    if len(_random_connetions) == 0:
        return barcode2, barcode_distance(barcode1, barcode2)
    return random.choice(_random_connetions), 1


for point in codes_table.values():
    if point.barcode in points_by_distance_table:
        continue
    logger.info("Sorting points...")
    points_by_distance_table[point.barcode] = sorted(
        [__point.barcode for __point in codes_table.values() if __point.barcode != point.barcode],
        key=lambda _point: find_next_in_path(point.barcode, _point)[1]
    )
    logger.info("DONE Sorting points...")

logger.info("points_by_distance_table: %s", len(points_by_distance_table))

def animal_new_target(animal, old_location=None):
    if animal.location in codes_table:
        used_real_targets = [_sp_animal.real_target for _sp_animal in  spawned_animals_table.values() if _sp_animal.real_target]
        used_real_targets.append(animal.location)
        available_targets = [_barcode for _barcode in codes_table.keys() if _barcode not in used_real_targets and _barcode not in ANIMAL_SKIP_CODES]
        if len(available_targets) > 0:
            available_targets = sorted(available_targets, key=lambda _barcode: barcode_distance(animal.location, _barcode))[:3]
            animal.real_target = random.choice(available_targets)

    animal.target = find_next_in_path(animal.location, animal.real_target)[0]
    distance = barcode_distance(animal.location, animal.target)
    logger.info("Animal %s new target %s, distance %s", animal.slug, animal.target, distance)
    animal.target_time = datetime.datetime.now() + datetime.timedelta(seconds=(distance * 5))


def handle_animal_spawns(to_spawn):
    logger.info("Spawning %s animals", to_spawn)
    available_animals = [
        animal for animal in animals_table.values()
        if animal.slug not in active_animals_table and animal.slug not in spawned_animals_table and animal.spawns
    ]
    to_spawn = random.choices(available_animals, k=to_spawn)
    for animal in to_spawn:
        animal.spawned = True
        animal.shiny = random.randint(0, 100) < 10
        animal.location = random.choice(list(codes_table.keys()))
        animal_new_target(animal)
        animal.timeout = datetime.datetime.now() + datetime.timedelta(seconds=random.randint(60, ANIMAL_TIMEOUT))
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
            if animal.target == animal.real_target and animal.location != animal.target:
                # Reached real target, stay a while
                animal.target_time = datetime.datetime.now() + datetime.timedelta(seconds=random.randint(50, 60))
                point = get_point(animal.target)
                handle_fruit_collected(point, timeout=True)
                point.fruit_timeout = animal.target_time
                point.fruit = 'animal-{}'.format(animal.slug)
                codes_table[point.barcode] = point
                animal.location = animal.target
            else:
                old_location = animal.location
                animal.location = animal.target
                animal_new_target(animal, old_location=old_location)
            spawned_animals_table[animal.slug] = animal


def handle_animal_evolve(animal):
    if animal.evolution:
        animal.active = False
        fruit_slug = animal.fruit_slug
        shiny = animal.shiny or False
        animal.fruit = 0
        animal.spawns = False
        animals_table[animal.slug] = animal
        active_animals_table.pop(animal.slug)
        animal = animals_table[animal.evolution]
        animal.shiny = shiny
        animal.active = True
        animal.fruit = 0
        animal.filled = False
        animal.fruit_slug = fruit_slug
        active_animals_table[animal.slug] = animal
    else:
        active_animals_table.pop(animal.slug)
        shelved_animals_table[animal.slug] = animal
        animal.spawns = False
        animals_table[animal.slug] = animal


def handle_animal_eating(animal):
    if animal.timeout and animal.timeout < datetime.datetime.now():
        logger.info("Animal %s timeout", animal.slug)
        animal.timeout = None
        animal.active = False
        active_animals_table.pop(animal.slug)
        return

    if not animal.egg:
        if not animal.fruit or animal.fruit < 1:
            animal.fruit = 0
        elif animal.start_eating < (datetime.datetime.now() - datetime.timedelta(seconds=animal.eating_speed)):
            animal.fruit = animal.fruit - 1
            animal.timeout = datetime.datetime.now() + datetime.timedelta(seconds=ANIMAL_TIMEOUT)
            animal.start_eating = datetime.datetime.now()
            logger.info("%s ate a %s: %s left", animal.name, animal.fruit_slug, animal.fruit)
            animal.experience += 1
        animal.level = int(animal.experience)
        if animal.level >= 1:
            animal.filled = True

    active_animals_table[animal.slug] = animal


def handle_animal_collected(animal):
    animal.active = True
    animal.fruit = 0
    animal.spawned = False
    animal.timeout = datetime.datetime.now() + datetime.timedelta(seconds=ANIMAL_TIMEOUT)
    fruits_available = [slug for slug in FRUIT_SLUGS]
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
    tick_enabled = True
    if main_table['last_tick'] and main_table['last_tick'] > datetime.datetime.now() - datetime.timedelta(seconds=3):
        tick_enabled = False
    else:
        main_table['last_tick'] = datetime.datetime.now()

    if tick_enabled:
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

    maps = table_to_dict(maps_table)
    for key in maps:
        codes[key] = maps[key]
        codes[key]['map_point'] = True

    spawned_animals = table_to_dict(spawned_animals_table)
    for key in spawned_animals:
        if spawned_animals[key]["timeout"]:
            spawned_animals[key]["close_to_timeout"] = spawned_animals[key]["timeout"] < (datetime.datetime.now() + datetime.timedelta(seconds=ANIMAL_CLOSE_TIMEOUT))
        spawned_animals[key]["seconds_to_target"] = ((spawned_animals[key]["target_time"] - datetime.datetime.now()).total_seconds()) + 2.0

    active_animals = table_to_dict(active_animals_table)
    for key in active_animals:
        if active_animals[key]["timeout"]:
            active_animals[key]["close_to_timeout"] = active_animals[key]["timeout"] < (datetime.datetime.now() + datetime.timedelta(seconds=ANIMAL_CLOSE_TIMEOUT))

    return {
        "codes": codes,
        "players": table_to_dict(players_table),
        "powerups": table_to_dict(powerups_table),
        "animals": active_animals,
        "spawned_animals": spawned_animals,
        "shelved_animals": table_to_dict(shelved_animals_table),
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
        if point.super_fruit or 'super_fruits' in active_powerups():
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
            ret = ""

    if point.barcode == 'http://koodi-10':
        for animal in active_animals_table.values():
            if animal.filled:
                will_evolve = bool(animal.evolution)
                handle_animal_evolve(animal)
                if will_evolve:
                    ret = "{} kehittyi!".format(animal.name)
                else:
                    ret = "{} laitettu talteen".format(animal.name)
                break

    if point.fruit:
        handle_fruit_collected(point)

    for key, animal in spawned_animals_table.items():
        if animal.real_target == point.barcode:
            handle_animal_collected(animal)
            ret += ' sait kiinni auton ' + animal.name + '!'

    points_by_distance = [codes_table[_barcode] for _barcode in points_by_distance_table[point.barcode]]

    for _point in points_by_distance:
        if _point.fruit and _point.fruit.startswith('animal-'):
            ret += '. Ota kiinni auto {}!'.format(point_names.get(_point.barcode))
            break
    else:
        for _point in points_by_distance:
            if _point.fruit:
                ret += '. Jotain kiinnostavaa olisi {}'.format(point_names.get(_point.barcode))
                break

    filled_animals = []
    for animal in active_animals_table.values():
        if animal.filled:
            filled_animals.append(animal)

    if len(filled_animals) == 1:
        ret += ". Autolla {} on maha täynnä".format(animal.slug)
    elif len(filled_animals) > 1:
        ret += ". Autoilla {} on maha täynnä".format(', '.join(animal.slug for animal in filled_animals[:-1]) + ' ja ' + filled_animals[-1].slug)

    return ret
