import io
import os
import random

from flask import Response, send_file, request, redirect
from dha_poc.util import build_media_filepath
from dha_poc.start import flask_app
from dha_poc.url_manager.blueprint import img_url_manager_v1, data_url_manager_v1
from dha_poc.ads_creator.creator import AdDataBundle, StandardAdGenerator
from dha_poc.url_manager.manager import ImageURLManager, RecommendationContext
from webargs.flaskparser import use_args


@img_url_manager_v1.route('/<string:encrypted_id>/<int:num>')
def img_req_processor_v2(encrypted_id, num):
    args = request.args
    context = RecommendationContext.from_encrypted_id(encrypted_id)
    ad_to_show = context.get_ad(num, args)
    if not ad_to_show:
        return '', 404
    resp = send_img_by_binary(ad_to_show)
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = 0
    return resp


def send_img_by_filename(filename):
    if not os.path.isfile(filename):
        return '', 404

    def generate():
        with open(filename, 'rb') as img:
            data = img.read(1024)
            while data:
                yield data
                data = img.read(1024)
    return Response(generate(), mimetype='image/png')


def send_img_by_binary(image):
    return send_file(io.BytesIO(image), mimetype='image/png')


@data_url_manager_v1.route('/<string:encrypted_id>/<int:num>')
def data_req_processor(encrypted_id, num):
    context = RecommendationContext.from_encrypted_id(encrypted_id)
    hotel = context.get_hotel(num)
    if not hotel:
        return '', 404
    template = flask_app.config['HOTEL_SITE_REDIRECT_URL_TEMPLATE']
    url = template.format(**{
        'hotel_id': hotel.get('id', None),
        'location_id': hotel.get('cityId', None),
        'hotel_lang': hotel.get('language', 'es-US'),
        'hotel_currency': hotel.get('currency', 'usd')
    })
    return redirect(url, code=303)
