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
monster_table = SqliteDict(os.path.join(data_folder, 'main.db'), tablename="monster", autocommit=True)

monster_table["target_time"] = datetime.datetime.now()
monster_table["start_time"] = datetime.datetime.now()
monster_table["respawn"] = datetime.datetime.now()
monster_table["status"] = "dead"

if main_table.get('origin') is None:
    main_table['origin'] = [0, 0]


# players_table["testplayer"] = {
#     "history": ["http://koodi-2"],
#     "ip_address": "ip_address",
#     "last_seen": datetime.datetime.now(),
# }


def _init_row(barcode=''):
    return {
        'barcode': barcode,
        'x': 0,
        'y': 0,
        'name': None
    }

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


def secs_to_monster_location(location, target, secs_to_location_base):
    return secs_to_location_base + (
        distance(codes_table[location]["x"], codes_table[location]["y"], codes_table[target]["x"], codes_table[target]["y"])
    ) * 5


def new_monster_location():
    history = monster_table.get("history", [])
    if not monster_table.get("location"):
        monster_table["target"] = random.choice(
            [code for code in codes_table.keys() if code != monster_table["location"]]
        )
    else:
        locations_with_distance = []
        for barcode, point in codes_table.items():
            if barcode in history:
                continue
            if barcode != monster_table.get("location"):
                monster_location = codes_table[monster_table.get("location")]
                locations_with_distance.append({
                    "code": barcode,
                    "distance": distance(point["x"], point["y"], monster_location["x"], monster_location["y"])
                })
        sorted_codes = [
            location["code"]
            for location in sorted(locations_with_distance, key=lambda x: x["distance"])
        ]
        # Pick one of the three closest locations NOT YET VISITED
        monster_table["target"] = random.choice(
            sorted_codes[:3]
        )

    history.append(monster_table["target"])
    if len(history) >= len(list(codes_table.values())):
        history = [monster_table["target"]]
    monster_table["history"] = history
    monster_table["secs_to_location_base"] += 0.1
    monster_table["secs_to_location"] = secs_to_monster_location(
        monster_table["location"], monster_table["target"], monster_table["secs_to_location_base"]
    )
    logger.info("secs_to_location: %s", monster_table["secs_to_location"])
    monster_table["start_time"] = datetime.datetime.now()
    monster_table["target_time"] = (
        datetime.datetime.now() +
        datetime.timedelta(seconds=monster_table["secs_to_location"])
    )
    logger.info("new_monster_location target to %s", monster_table["target"])


def respawn_monster():
    monster_table["status"] = "alive"
    monster_table["secs_to_location_base"] = 1
    monster_table["secs_to_location"] = secs_to_monster_location(
        monster_table["location"], monster_table["target"], monster_table["secs_to_location_base"]
    )
    monster_table["location"] = random.choice(list(codes_table.keys()))
    logger.info("respawn_monster to %s", monster_table["location"])
    
    new_monster_location()


def kill_monster(player):
    monster_table["status"] = "dead"
    monster_table["secs_to_location"] = 0
    monster_table["location"] = None
    monster_table["target"] = None
    monster_table["respawn"] = datetime.datetime.now() + datetime.timedelta(seconds=30)
    kills = monster_table.get("kills", []) or []
    kills.append({
        "time": datetime.datetime.now().isoformat(),
        "player": player["ip_address"]
    })
    monster_table["kills"] = kills
    logger.info("monster killed by %s", player)


@app.route("/api/tick")
def game_tick():
    if monster_table.get("status", "dead") == "dead":
        if datetime.datetime.now() > monster_table["respawn"]:
            respawn_monster()
    else:
        if datetime.datetime.now() > monster_table["target_time"]:
            monster_table["location"] = monster_table["target"]
            new_monster_location()
    
    dead_players = []
    for key, player in players_table.items():
        if not player.get("last_seen") or (player["last_seen"] < datetime.datetime.now() - datetime.timedelta(minutes=10)):
            dead_players.append(key)

    for key in dead_players:
        del players_table[key]

    monster = dict(monster_table)
    monster["start_time"] = monster["start_time"].isoformat()
    monster["target_time"] = monster["target_time"].isoformat()
    monster["respawn"] = monster["respawn"].isoformat()
    return {
        "codes": dict(codes_table),
        "players": dict(players_table),
        "monster": monster,
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

    kill = False
    if barcode == monster_table.get("target"):
        kill_monster(player)
        kill = True

    logger.info("player visited %s", barcode)
    return '1' if kill else '0'
