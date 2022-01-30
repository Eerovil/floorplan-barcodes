from flask import Flask
from sqlitedict import SqliteDict

app = Flask(__name__)

codes_table = SqliteDict('/data/main.db', tablename="codes", autocommit=True)

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"

