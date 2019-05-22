import re
import os

from flask import request, jsonify, current_app
from functools import wraps
from dha_poc.start import flask_app


ERROR_OBJ = {'error': 'access1 denied'}

zipcode_regex = re.compile(r'^\d{5}$')
coordinates_regex = re.compile(r'^(\-?\d+(\.\d+)?),\s*(\-?\d+(\.\d+)?)$')
sort_criteria = re.compile(r'^(:?\w+,?)+$')
dimensions_regex = re.compile(r'^\dddx\ddd$')


def token_required(f):
    @wraps(f)
    def token_validator(*args, **kwargs):
        token = request.args.get('token', None)        
        if not token or token != current_app.config.get('TOKEN', None):
            return jsonify(ERROR_OBJ)
        return f(*args, **kwargs)
    return token_validator


def build_media_filepath(*args):
    sep = os.path.sep
    path_end = sep.join(args)
    return os.path.join(flask_app.config['MEDIA_DIR'], path_end)


def generate_photo_url(hotel_id, group_id, photo_num, width, height, crop=False):
    template = flask_app.config['HOTEL_PHOTO_URL_TEMPLATE']
    type = 'crop' if crop else 'limit'
    return template.format(hotel_id, group_id, photo_num, width, height, type)


def generate_hotel_price_url(city_id, check_in, check_out, currency='usd', language='en'):
    template = flask_app.config['HOTEL_PRICE_DATA_URL_TEMPLATE']
    return template.format(currency, language, city_id, check_in, check_out, flask_app.config['HOTEL_DATA_API_TOKEN'])


def generate_prefixed_url(prefix):
    port = flask_app.config.get('PORT', None)
    if not port:
        template = '{protocol}://{hostname}{prefix}'
    else:
        template = '{protocol}://{hostname}:{port}{prefix}'
    return template.format(**{
        'hostname': flask_app.config['HOSTNAME'],
        'protocol': flask_app.config['PROTOCOL'],
        'port': port,
        'prefix': prefix
    })
