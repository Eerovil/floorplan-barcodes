from flask import Flask, render_template, request
from sqlitedict import SqliteDict
import os

data_folder = '/data'
if not os.path.exists(data_folder):
    data_folder = '../data'

app = Flask(__name__, static_url_path='/static', static_folder=data_folder, template_folder='')

codes_table = SqliteDict(os.path.join(data_folder, 'main.db'), tablename="codes", autocommit=True)
main_table = SqliteDict(os.path.join(data_folder, 'main.db'), tablename="main", autocommit=True)
players_table = SqliteDict(os.path.join(data_folder, 'main.db'), tablename="players", autocommit=True)


if main_table.get('origin') is None:
    main_table['origin'] = [0, 0]


def _init_row(barcode=''):
    return {
        'barcode': barcode,
        'x': 0,
        'y': 0,
        'name': None
    }


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


@app.route("/api/list")
def list_barcodes():
    return dict(codes_table)


@app.route("/api/players")
def list_players():
    return dict(players_table)


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
            "history": []
        }
    if len(player["history"]) > 0:
        if player["history"][-1] == barcode:
            return 'same'
    player["history"].append(barcode)
    player["history"] = player["history"][-4:]
    players_table[ip_address] = player

    return player