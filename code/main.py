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


def new_monster_location():
    monster_table["target"] = random.choice(
        [code for code in codes_table.keys() if code != monster_table["location"]]
    )
    monster_table["secs_to_location"] += 1
    monster_table["start_time"] = datetime.datetime.now()
    monster_table["target_time"] = (
        datetime.datetime.now() +
        datetime.timedelta(seconds=monster_table["secs_to_location"])
    )
    logger.info("new_monster_location target to %s", monster_table["target"])


def respawn_monster():
    monster_table["status"] = "alive"
    monster_table["secs_to_location"] = 4
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
        }

    player["history"].append(barcode)
    player["history"] = player["history"][-4:]
    players_table[ip_address] = player

    if barcode == monster_table.get("target"):
        kill_monster(player)

    logger.info("player visited %s", barcode)
    return player