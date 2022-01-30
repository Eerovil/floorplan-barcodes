from flask import Flask, render_template, request
from sqlitedict import SqliteDict

app = Flask(__name__, static_url_path='/static', static_folder='/data', template_folder='')

codes_table = SqliteDict('/data/main.db', tablename="codes", autocommit=True)
main_table = SqliteDict('/data/main.db', tablename="main", autocommit=True)
players_table = SqliteDict('/data/main.db', tablename="players", autocommit=True)


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
    return {
        "codes": dict(codes_table),
        "players": dict(players_table),
    }


@app.route("/api/mark")
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
    if len(player["history"] > 0):
        if player["history"][-1] == barcode:
            return 'same'
    player["history"].append(barcode)
    players_table[ip_address] = player

    return player