from ctypes import pointer
from flask import Flask, render_template, request
from sqlitedict import SqliteDict
import os
import datetime
import random
import logging

data_folder = '/data'
if not os.path.exists(data_folder):
    data_folder = '../data'

app = Flask(__name__, static_url_path='/static', static_folder=data_folder, template_folder='')
logger = app.logger

codes_table = SqliteDict(os.path.join(data_folder, 'main.db'), tablename="codes", autocommit=True)
main_table = SqliteDict(os.path.join(data_folder, 'main.db'), tablename="main", autocommit=True)
players_table = SqliteDict(os.path.join(data_folder, 'main.db'), tablename="players", autocommit=True)
animals_table = SqliteDict(os.path.join(data_folder, 'main.db'), tablename="animals", autocommit=True)

# players_table["testplayer"] = {
#     "history": ["http://koodi-2"],
#     "ip_address": "ip_address",
#     "last_seen": datetime.datetime.now(),
# }

if True or 'mouse' not in animals_table:
    animals_table['mouse'] = {
        "name": "Hiiri",
        "slug": "mouse",
        "image": "mouse.png",
        "fruit_slug": "apple",
        "fruit": 5,
        "eating_speed": 15,  # seconds
        "start_eating": datetime.datetime.now(),
    }

if 'bunny' in animals_table:
    del animals_table['bunny']

def _init_row(barcode=''):
    return {
        'barcode': barcode,
        'x': 0,
        'y': 0,
        'name': None,
        'fruit': None,
        'fruit_death': datetime.datetime.now(),
    }


for orig_key, point in codes_table.items():
    initial_row = _init_row()
    for key in initial_row.keys():
        if key not in point:
            point[key] = initial_row[key]
    codes_table[orig_key] = point
    logger.info("Initializing code %s: %s", orig_key, point.keys())


INITIAL_CODES = [
    'http://koodi-1',
    'http://koodi-2',
    'http://koodi-3',
    'http://koodi-4',
    'http://koodi-5',
    'http://koodi-6',
    'http://koodi-7',
    'http://koodi-8',
]
for initial_code in INITIAL_CODES:
    if initial_code not in codes_table:
        codes_table[initial_code] = _init_row(initial_code)


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
    row['barcode'] = barcode
    codes_table[barcode] = row
    return row


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
    row['x'] = x
    row['y'] = y
    if name:
        row['name'] = name
    codes_table[barcode] = row
    return row


def distance(x1, y1, x2, y2):
    return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5


def handle_fruit_collected(point):
    for key, animal in animals_table.items():
        if animal['fruit_slug'] == point['fruit']:
            logger.info("Fruit collected: %s at %s", point['fruit'], point['barcode'])
            if animal["fruit"] == 0:
                animal["start_eating"] = datetime.datetime.now()
            animal['fruit'] += 1
            animals_table[animal["slug"]] = animal
            point['fruit'] = None
            point['fruit_death'] = datetime.datetime.now()
            codes_table[point['barcode']] = point
            break
    else:
        logger.warning("Fruit %s not found in animals table", point['fruit'])

def respawn_fruit(point):
    fruit_slugs = list(set([animal["fruit_slug"] for animal in animals_table.values()]))
    point['fruit'] = random.choice(fruit_slugs)
    logger.info("Fruit respawned at code %s: %s", point['barcode'], point['fruit'])
    codes_table[point['barcode']] = point


@app.route("/api/tick")
def game_tick():
    for key, point in codes_table.items():
        if point.get('fruit'):
            continue
        if not point['fruit_death'] or point['fruit_death'] < (datetime.datetime.now() - datetime.timedelta(seconds=60)):
            respawn_fruit(point)

    for key, animal in animals_table.items():
        if not animal['fruit'] or animal['fruit'] < 1:
            animal['fruit'] = 0
            continue
        if animal['start_eating'] < (datetime.datetime.now() - datetime.timedelta(seconds=animal['eating_speed'])):
            animal['fruit'] = animal['fruit'] - 1
            animal['start_eating'] = datetime.datetime.now()
            logger.info("%s ate a %s: %s left", animal['name'], animal['fruit_slug'], animal["fruit"])
        animals_table[animal["slug"]] = animal

    
    dead_players = []
    for key, player in players_table.items():
        if not player.get("last_seen") or (player["last_seen"] < datetime.datetime.now() - datetime.timedelta(minutes=10)):
            dead_players.append(key)

    for key in dead_players:
        del players_table[key]

    return {
        "codes": dict(codes_table),
        "players": dict(players_table),
        "animals": dict(animals_table),
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
        player = {
            "history": [],
            "ip_address": ip_address,
            "last_seen": datetime.datetime.now(),
        }

    player["history"].append(barcode)
    player["history"] = player["history"][-4:]
    players_table[ip_address] = player

    point = codes_table[barcode]
    got_one = False
    if point['fruit']:
        handle_fruit_collected(point)
        got_one = True

    logger.info("player visited %s", barcode)
    return '1' if got_one else '0'
