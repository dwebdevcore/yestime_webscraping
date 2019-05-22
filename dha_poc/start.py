from flask import Flask
from dha_poc.config import Config
from flask_redis import FlaskRedis


flask_app = Flask(__name__)
flask_app.config.from_object(Config)

redis_store = FlaskRedis(flask_app)



if flask_app.config.get('ENVIRONMENT') == 'DEBUG':
    flask_app.debug = True
