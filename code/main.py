from flask import Flask, render_template, request
from sqlitedict import SqliteDict
import os
import datetime
import random
import logging
from decimal import Decimal


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

pokemons_table = SqliteDict(os.path.join(data_folder, 'pokemons.db'), tablename="pokemons", autocommit=False)

FRUIT_SLUGS = ['watermelon', 'carrot', 'apple', 'sandvich']

main_table['last_tick'] = datetime.datetime.now()

class Animal(BaseModel):
    active = False
    spawned = False
    spawns = True
    id: int
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
    egg = False
    index = 0

    def __init__(self, **data):
        if not data.get('id'):
            data['id'] = len(animals_table)
        super().__init__(**data)

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
powerups_table['sun'] = Powerup(
    slug='sun',
    name='Lisää hedelmiä',
    duration=0,
    cooldown=0,
    active=False,
    available=True,
    start_time=datetime.datetime.now() - datetime.timedelta(days=1),
)


# Load pokemons
for animal_id in list(animals_table.keys()):
    del animals_table[animal_id]

for animal_id in list(active_animals_table.keys()):
    del active_animals_table[animal_id]

for animal_id in list(spawned_animals_table.keys()):
    del spawned_animals_table[animal_id]

for animal_id in list(shelved_animals_table.keys()):
    del shelved_animals_table[animal_id]

for pokemon_name, pokemon in pokemons_table.items():
    front_default = os.path.join(data_folder, pokemon_name, 'animated', 'front_default.gif')
    if not os.path.exists(front_default):
        logger.info("Skipping pokemon %s, no images", pokemon_name)
        continue
    
    pokemon_number = pokemon['api_url'].split('/')[-2]

    animals_table[pokemon_name] = Animal(
        slug=pokemon_name,
        name=pokemon_name.capitalize(),
        fruit_slug=FRUIT_SLUGS[(len(animals_table) % len(FRUIT_SLUGS))],
        fruit=0,
        eating_speed=15,
        experience=0,
        level=0,
        start_eating=datetime.datetime.now(),
        last_source=None,
        evolution=pokemon.get('evolution'),
        location=None,
        target=None,
        target_time=None,
        filled=False,
        index=int(pokemon_number),
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



animals_table["burglar"] = Animal(
    slug="burglar",
    name="Varas",
    fruit_slug='watermelon',
    fruit=0,
    eating_speed=15,
    experience=0,
    level=0,
    start_eating=datetime.datetime.now(),
    last_source=None,
    evolution=None,
    location=None,
    target=None,
    target_time=None,
    filled=False
)
logger.info("Added burglar")



FRUIT_TIMEOUT = 60
ANIMAL_TIMEOUT = 7 * 60
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
        'fruit_timeout': None,
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
ANIMAL_SKIP_CODES = ['http://koodi-6']
for initial_code in INITIAL_CODES:
    if initial_code not in codes_table:
        codes_table[initial_code] = _init_row(initial_code)


point_names = {
    'http://koodi-1': 'Eteisessä',
    'http://koodi-2': 'Sohvan takana',
    'http://koodi-3': 'Savupiipussa',
    'http://koodi-4': 'Vaatehuoneessa',
    'http://koodi-5': 'Jääkaapissa',
    'http://koodi-6': 'Telkkarin Luona',
    'http://koodi-7': 'Kuivausrummussa',
    'http://koodi-8': 'Einarin Huoneessa',
    'http://koodi-9': 'Saunassa',
    'http://koodi-10': 'Makuuhuoneessa',
    'http://koodi-11': 'Valtterin huoneessa',
    'http://koodi-12': 'Kodinhoitohuoneessa',
}



play_area_limits = [
    set([
        'http://koodi-2',
        'http://koodi-5',
        # Lisäsiipi
        'http://koodi-6',
        'http://koodi-7',
        'http://koodi-8',
        'http://koodi-3',
    ]),
    set([
        # Lisäsiipi
        'http://koodi-6',
        'http://koodi-7',
        'http://koodi-8',
        'http://koodi-3',
    ]),
]

main_table['PLAY_AREA'] = 30
main_table['ACTIVE_PLAYING_START'] = None
main_table['ACTIVE_PLAYING_CURRENT'] = None

def get_not_play_area_codes():
    if main_table['PLAY_AREA'] > len(play_area_limits) - 1:
        return []
    return [code for code in codes_table.keys() if code in play_area_limits[main_table['PLAY_AREA']]]


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
    return float(((Decimal(x1) - Decimal(x2)) ** 2 + (Decimal(y1) - Decimal(y2)) ** 2) ** Decimal(0.5))


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
                if powerup.slug == 'sun':
                    # Spawn one of each fruit type (or try to)
                    animal_destinations = [animal.real_target for animal in spawned_animals_table.values()]
                    for fruit_slug in FRUIT_SLUGS:
                        for _point in sorted(codes_table.values(), key=lambda _: random.random()):
                            if _point.barcode in animal_destinations:
                                continue
                            if not _point.fruit:
                                respawn_fruit(_point, fruit_slug=fruit_slug)
                                break
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
                active_animals_table[animal.id] = animal
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


def respawn_fruit(point, powerup_only=False, fruit_slug=None):
    powerups = []
    for powerup_slug, powerup in powerups_table.items():
        if powerup.active or not powerup.available:
            continue
        if powerup.start_time + datetime.timedelta(seconds=powerup.cooldown) > datetime.datetime.now():
            continue
        if powerup.slug == "sun":
            if len(list(_point for _point in codes_table.values() if _point.fruit and not _point.fruit.startswith("animal"))) > 1:
                # Sun is available only if just one or no fruit is on the map
                continue
        if powerup.slug == "super_fruits":
            if len(list(_point for _point in codes_table.values() if _point.fruit and not _point.fruit.startswith("animal") and point.fruit != "sun")) == 0:
                # super_fruits is available only if fruits are on the map
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
        if powerup.slug == "sun":
            # Sun is never hidden as gift
            point.gift = False
        point.fruit_timeout = datetime.datetime.now() + datetime.timedelta(seconds=FRUIT_TIMEOUT)
    elif not powerup_only:
        if fruit_slug:
            fruit_slugs = [fruit_slug]
        else:
            fruit_slugs = list(set([animal.fruit_slug for animal in active_animals_table.values()]))
        if len(fruit_slugs) > 0:
            point.fruit = random.choice(fruit_slugs)
            point.super_fruit = random.randint(0, 100) < 10
            point.fruit_timeout = None
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
    if animal.slug == "burglar" or animal.location in codes_table:
        # Animal is in a "bush"
        used_real_targets = [_sp_animal.real_target for _sp_animal in spawned_animals_table.values() if _sp_animal.real_target]
        if animal.slug == "burglar":
            used_real_targets = []  # Burglar can go anywhere
        used_real_targets.append(animal.location)

        available_targets = []
        if animal.slug == "burglar":
            # Try to direct burglar towards a fruit
            available_targets = [
                code.barcode for code in codes_table.values()
                if (
                    code.fruit and
                    not code.fruit.startswith('animal-') and
                    code.barcode not in used_real_targets and
                    code.barcode not in ANIMAL_SKIP_CODES and
                    code.barcode not in get_not_play_area_codes()
                )
            ]

            logger.info("Burglar available_targets: %s", available_targets)
            if len(available_targets) == 0:
                logger.info("Burglar can't find any fruit, trying to find any point")
                # If no fruit, try to direct burglar towards an animal
                available_targets = [code.barcode for code in codes_table.values() if code.fruit and code.barcode not in used_real_targets and code.barcode not in ANIMAL_SKIP_CODES and code.barcode not in get_not_play_area_codes()]

        if len(available_targets) == 0:
            available_targets = [_barcode for _barcode in codes_table.keys() if _barcode not in used_real_targets and _barcode not in ANIMAL_SKIP_CODES and _barcode not in get_not_play_area_codes()]

        if len(available_targets) > 0:
            available_targets = sorted(available_targets, key=lambda _barcode: barcode_distance(animal.location, _barcode))[:3]
            if animal.slug == "burglar":
                animal.real_target = available_targets[0]
            else:
                animal.real_target = random.choice(available_targets)

    animal.target = find_next_in_path(animal.location, animal.real_target)[0]
    distance = barcode_distance(animal.location, animal.target)
    logger.info("Animal %s new target %s, distance %s", animal.slug, animal.target, distance)
    animal.target_time = datetime.datetime.now() - datetime.timedelta(seconds=1) + datetime.timedelta(seconds=(distance * 4))
    if animal.slug == "burglar":
        # Burglar is faster
        animal.target_time = datetime.datetime.now() - datetime.timedelta(seconds=1) + datetime.timedelta(seconds=(distance * 1.5))


def handle_animal_spawns(to_spawn):
    logger.info("Spawning %s animals", to_spawn)
    unique_shleved_animals = set()
    for shelved_animal in shelved_animals_table.values():
        unique_shleved_animals.add(shelved_animal.slug)
    unique_shleved_animals = len(unique_shleved_animals) - 1
    if unique_shleved_animals < 0:
        unique_shleved_animals = 0
    
    unique_animals = list()
    used_slugs = set()
    for animal in animals_table.values():
        if animal.slug not in used_slugs:
            unique_animals.append(animal)
            used_slugs.add(animal.slug)

    available_slugs = (
        list([
            animal.slug
            for animal in sorted(
                unique_animals,
                key=lambda _animal: _animal.index
            )
            if animal.spawns and animal.index
        ])[unique_shleved_animals:unique_shleved_animals+3]
    )

    for animal in spawned_animals_table.values():
        if animal.slug == "burglar":
            break
    else:
        available_slugs += ["burglar"]

    # Count unspanwed, initialized animals
    available_animals = [
        animal for animal in animals_table.values()
        if (
            animal.id not in active_animals_table and
            animal.id not in spawned_animals_table and
            animal.spawns and
            animal.slug in available_slugs
        )
    ]

    if len(available_animals) < to_spawn:
        logger.info("Not enough animals to spawn, initializing more")
        for _ in range(to_spawn - len(available_animals)):
            animal_slug = random.choice(available_slugs)
            animal = [
                _animal for _animal in animals_table.values()
                if _animal.slug == animal_slug
            ][0]
            animal = animal.copy()
            animal.id = len(animals_table)
            animals_table[animal.id] = animal
            available_animals.append(animal)

    if any(animal.slug == 'burglar' for animal in available_animals):
        burglar = [animal for animal in available_animals if animal.slug == 'burglar'][0]
        to_spawn = random.choices(available_animals, k=(to_spawn - 1)) + [burglar]
    else:
        to_spawn = random.choices(available_animals, k=to_spawn)
    for animal in to_spawn:
        animal.spawned = True
        animal.shiny = random.randint(0, 100) < 10
        animal.location = random.choice(list(codes_table.keys()))
        animal_new_target(animal)
        animal.timeout = datetime.datetime.now() + datetime.timedelta(seconds=random.randint(60, ANIMAL_TIMEOUT))
        animals_table[animal.id] = animal
        spawned_animals_table[animal.id] = animal
        logger.info("Animal spawned: %s", animal.slug)


def handle_spawned_animal(animal):
    if animal.timeout and animal.timeout < datetime.datetime.now() and animal.slug != "burglar":
        logger.info("Animal %s: %s timeout", animal.slug, animal.id)
        animal.timeout = None
        animal.spawned = False
        spawned_animals_table.pop(animal.id)
        return

    if animal.target and animal.target_time:
        if animal.target_time <= datetime.datetime.now():
            if animal.target == animal.real_target and animal.location != animal.target:
                # Reached real target, stay a while
                animal.target_time = datetime.datetime.now() + datetime.timedelta(seconds=random.randint(50, 60))
                if animal.slug == "burglar":
                    animal.target_time = datetime.datetime.now() + datetime.timedelta(seconds=random.randint(2, 5))
                point = get_point(animal.target)
                if point.fruit and point.fruit.startswith('animal-'):
                    try:
                        stolen_animal = spawned_animals_table[point.fruit.replace('animal-', '')]
                        stolen_animal.timeout = datetime.datetime.now()
                        spawned_animals_table[stolen_animal.id] = stolen_animal
                        logger.info(
                            "Animal %s:%s stolen by %s", stolen_animal.slug, stolen_animal.id, animal.slug
                        )
                    except KeyError:
                        point.fruit = None

                handle_fruit_collected(point, timeout=True)
                point.fruit_timeout = animal.target_time or datetime.datetime.now()
                point.fruit = 'animal-{}'.format(animal.slug)
                codes_table[point.barcode] = point
                animal.location = animal.target
            else:
                old_location = animal.location
                animal.location = animal.target
                animal_new_target(animal, old_location=old_location)
            spawned_animals_table[animal.id] = animal


def handle_animal_evolve(animal):
    if animal.evolution:
        animal.active = False
        fruit_slug = animal.fruit_slug
        shiny = animal.shiny or False
        fruit_count = animal.fruit
        animal.fruit = 0
        animal.spawns = False
        animals_table[animal.id] = animal
        active_animals_table.pop(animal.id)
        animal = animals_table[animal.evolution]
        animal.shiny = shiny
        animal.active = True
        animal.egg = False
        animal.fruit = fruit_count - 1
        if animal.fruit < 0:
            animal.fruit = 0
        animal.filled = False
        animal.fruit_slug = fruit_slug
        active_animals_table[animal.id] = animal
    else:
        active_animals_table.pop(animal.id)
        shelved_animals_table[animal.id] = animal
        animal.spawns = False
        animals_table[animal.id] = animal


def handle_animal_eating(animal):
    if animal.timeout and animal.timeout < datetime.datetime.now():
        logger.info("Animal %s:%s timeout", animal.slug, animal.id)
        animal.timeout = None
        animal.active = False
        active_animals_table.pop(animal.id)
        return

    if not animal.fruit or animal.fruit < 1:
        animal.fruit = 0
    elif animal.start_eating < (datetime.datetime.now() - datetime.timedelta(seconds=animal.eating_speed)):
        animal.fruit = animal.fruit - 1
        animal.timeout = datetime.datetime.now() + datetime.timedelta(seconds=ANIMAL_TIMEOUT)
        animal.start_eating = datetime.datetime.now()
        logger.info("%s ate a %s: %s left", animal.name, animal.fruit_slug, animal.fruit)
        animal.experience += 1
    animal.level = int(animal.experience)
    if animal.level >= (int(animal.index / 10) + 1):
        animal.filled = True

    active_animals_table[animal.id] = animal


def handle_animal_collected(animal):
    if animal.slug == "burglar":
        # timeout a collected animal
        for key in (active_animals_table.keys()):
            animal_to_steal = active_animals_table[key]
            animal_to_steal.timeout = datetime.datetime.now()
            active_animals_table[key] = animal_to_steal
            break
        return
    animal.active = True
    animal.filled = False
    animal.fruit = 0
    animal.spawned = False
    animal.timeout = datetime.datetime.now() + datetime.timedelta(seconds=ANIMAL_TIMEOUT)
    fruits_available = [slug for slug in FRUIT_SLUGS]
    # Check active animals and pick one fruit not used yet for this animal
    for active_animal in active_animals_table.values():
        if active_animal.active and active_animal.fruit_slug in fruits_available:
            fruits_available.remove(active_animal.fruit_slug)
    active_animals_table[animal.id] = animal
    if animal.id in spawned_animals_table:
        del spawned_animals_table[animal.id]
    logger.info("%s collected: %s", animal.name, animal.fruit_slug)


def table_to_dict(_dict):
    return {key: dict(value) for key, value in _dict.items()}


@app.route("/api/tick")
def game_tick():

    if not main_table['ACTIVE_PLAYING_CURRENT'] or (main_table['ACTIVE_PLAYING_CURRENT'] - datetime.datetime.now()).total_seconds() > 5 * 60:
        main_table['ACTIVE_PLAYING_START'] = None
        main_table['ACTIVE_PLAYING_CURRENT'] = None
        main_table['PLAY_AREA'] = 30

    tick_enabled = True
    if main_table['last_tick'] and main_table['last_tick'] > datetime.datetime.now() - datetime.timedelta(seconds=3):
        tick_enabled = False
    else:
        main_table['last_tick'] = datetime.datetime.now()

    if tick_enabled:
        for key, point in codes_table.items():
            if point.fruit and point.fruit_timeout and point.fruit_timeout < datetime.datetime.now():
                handle_fruit_collected(point, timeout=True)
            if point.fruit:
                continue
            if point.barcode in get_not_play_area_codes():
                continue
            if not point.fruit_death or point.fruit_death < (datetime.datetime.now() - datetime.timedelta(seconds=30)):
                respawn_fruit(point, powerup_only=True)

        for key, powerup in powerups_table.items():
            if powerup.active and powerup.start_time + datetime.timedelta(seconds=powerup.duration) < datetime.datetime.now():
                powerup.active = False
                powerups_table[key] = powerup
                logger.info("Powerup %s expired", powerup.slug)

        for key, animal in active_animals_table.items():
            handle_animal_eating(animal)

        for key, animal in spawned_animals_table.items():
            handle_spawned_animal(animal)

        animal_to_spawn = 6 - len(spawned_animals_table) - len(active_animals_table)
        if animal_to_spawn > 0 and main_table['last_tick'] > datetime.datetime.now() - datetime.timedelta(seconds=10):
            # Only spawn animals every 10 seconds
            handle_animal_spawns(1)


        dead_players = []
        for key, player in players_table.items():
            if not player.last_seen or (player.last_seen < datetime.datetime.now() - datetime.timedelta(minutes=10)):
                dead_players.append(key)

        for key in dead_players:
            del players_table[key]

    codes = table_to_dict(codes_table)

    maps = table_to_dict(maps_table)
    for key in maps:
        codes[key] = maps[key]
        codes[key]['map_point'] = True

    spawned_animals = table_to_dict(spawned_animals_table)
    for key in spawned_animals:
        spawned_animals[key]["seconds_to_target"] = ((spawned_animals[key]["target_time"] - datetime.datetime.now()).total_seconds()) + 3.0

    active_animals = table_to_dict(active_animals_table)

    shaking = False
    if main_table.get('last_shake'):
        if (datetime.datetime.now() - main_table['last_shake']).total_seconds() < 1:
            shaking = True

    return {
        "codes": codes,
        "players": table_to_dict(players_table),
        "powerups": table_to_dict(powerups_table),
        "animals": active_animals,
        "spawned_animals": spawned_animals,
        "shelved_animals": table_to_dict(shelved_animals_table),
        "shaking": shaking,
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

    def pokemon_eats_fruit(fruit_slug):
        for animal in active_animals_table.values():
            if animal.fruit_slug == fruit_slug:
                return True
        return False


    if point.fruit:
        if point.fruit not in FRUIT_SLUGS or pokemon_eats_fruit(point.fruit):
            ret = 'Hyvä, löysit '
        else:
            ret = 'Nam, söit itse '
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
        elif point.fruit == 'sun':
            ret += 'Auringon! Hedelmiä kasvaa!'
        else:
            ret = ""

    if point.barcode == 'http://koodi-6':
        for animal in active_animals_table.values():
            if not animal.egg and animal.filled:
                will_evolve = bool(animal.evolution)
                handle_animal_evolve(animal)
                if will_evolve:
                    ret = "{} kehittyi!".format(animal.slug)
                else:
                    ret = "{} laitettu talteen".format(animal.slug)
                break

    if point.fruit:
        handle_fruit_collected(point)

    for key, animal in spawned_animals_table.items():
        if animal.real_target == point.barcode and animal.location == animal.real_target:
            handle_animal_collected(animal)
            if animal.slug == "burglar":
                ret += ' voi ei! Varas!'
            else:
                ret += ' sait munan!'

    points_by_distance = [codes_table[_barcode] for _barcode in points_by_distance_table[point.barcode]]

    for _point in points_by_distance:
        if _point.fruit and _point.fruit.startswith('animal-'):
            ret += '. Jotain olisi {}!'.format(point_names.get(_point.barcode))
            break
    else:
        for _point in points_by_distance:
            if _point.fruit:
                ret += '. Jotain olisi {}'.format(point_names.get(_point.barcode))
                break

    filled_animals = []
    for animal in active_animals_table.values():
        if animal.filled:
            filled_animals.append(animal)

    if len(filled_animals) == 1:
        ret += ". Pokemonilla {} on maha täynnä".format(filled_animals[0].slug)
    elif len(filled_animals) > 1:
        ret += ". Pokemoneilla {} on maha täynnä".format(', '.join(animal.slug for animal in filled_animals[:-1]) + ' ja ' + filled_animals[-1].slug)

    main_table['ACTIVE_PLAYING_CURRENT'] = datetime.datetime.now()
    if not main_table['ACTIVE_PLAYING_START']:
        main_table['ACTIVE_PLAYING_START'] = datetime.datetime.now()
    if (main_table['ACTIVE_PLAYING_CURRENT'] - main_table['ACTIVE_PLAYING_START']).total_seconds() > 4 * 60:
        main_table['PLAY_AREA'] = 1
    if (main_table['ACTIVE_PLAYING_CURRENT'] - main_table['ACTIVE_PLAYING_START']).total_seconds() > 12 * 60:
        main_table['PLAY_AREA'] = 2

    return ret


@app.route("/api/event", methods=['POST'])
def post_event():
    event = request.json.get("event")
    if not event:
        return 'No event provided'

    if event == 'shake':
        main_table['last_shake'] = datetime.datetime.now()
        logger.info("Got shake")
        for animal in active_animals_table.values():
            if animal.egg:
                animal.experience += 0.3
                animal.level = int(animal.experience)
                logger.info("level: %s", animal.experience)
                if animal.level >= 1:
                    animal.egg = False
                    animal.experience = 0
                    animal.level = 0
                active_animals_table[animal.id] = animal

    return 'ok'
