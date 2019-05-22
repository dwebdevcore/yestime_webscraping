import json

from datetime import date, datetime, timedelta
from flask import request, current_app, jsonify, send_file, render_template
from dha_poc.email_tools.email_sender import GmailMailer
from dha_poc.start import redis_store
from dha_poc.api.blueprint import api_v1
from dha_poc.util import token_required
from dha_poc.rec_engine.engine import StandardEngine
from dha_poc.ads_creator.creator import StandardAdGenerator, AdDataBundle
from dha_poc.url_manager.manager import ImageURLManager, RecommendationContext
from dha_poc.data.formatter import HotelDataFormatter
from dha_poc.data.hotel_api import HotelDataInterface
from webargs import core
from webargs.flaskparser import use_args
from webargs.fields import Str, Int, Bool
from dha_poc.util import zipcode_regex, coordinates_regex, sort_criteria, dimensions_regex
from dha_poc.data.hotel_attributes import available_languages

parser = core.Parser()


query_args = {
    'zipcode': Str(required=True, validate=lambda z: zipcode_regex.match(str(z)) is not None),
    'email': Str(),
    'price': Int(validate=lambda n: 0 <= n <= 10e6),
    'title': Str(validate=lambda s: len(s) < 1000),
    'language': Str(validate=lambda s: len(s) == 2 and s.lower() in available_languages),
    'currency': Str(validate=lambda s: len(s) == 3),
    'coord': Str(validate=lambda s: coordinates_regex.match(s)),
    'event_date': Str(),
    'num': Int(),
    'context_id': Int()
}

update_args = {
    'context_id': Int(required=True),
    'zipcode': Str(validate=lambda z: zipcode_regex.match(str(z)) is not None),
    'sort_criteria': Str(validate=lambda s: sort_criteria.match(str(s)) is not None),
    'descending': Bool()
}

img_tag = {
    'zipcode': Str(validate=lambda z: zipcode_regex.match(str(z)) is not None),
    'sort_criteria': Str(validate=lambda s: sort_criteria.match(str(s)) is not None),
    'descending': Bool(),
    'rank': Int(validate=lambda z: 1 <= z <= 4),
    'dimensions': Str(),
    'imgAttr': Str()
}


@api_v1.route('/rec', methods=['GET'])
@token_required
@use_args(query_args, locations=('query',))
def recommendation(args):
    hotel_recommendations = StandardEngine.query(args)
    if not hotel_recommendations:
        return jsonify({'status': 'No hotels could be found for the provided zipcode'})
    formatted_hotels = HotelDataFormatter.format_hotel_data(hotel_recommendations, args)
    return jsonify(formatted_hotels)


@api_v1.route('/rec_test', methods=['GET'])
@token_required
@use_args(query_args, locations=('query',))
def debug(args):
    interface = HotelDataInterface.get_instance()
    hotels = interface.get_hotels_by_zipcode(args.get('zipcode'), args)
    return jsonify(hotels)


@api_v1.route('/rec_debug', methods=['GET'])
@token_required
@use_args(query_args, locations=('query',))
def recommendation_as_json(args):
    hotel_recommendations = StandardEngine.query(args)
    if not hotel_recommendations:
        return jsonify({'status': 'No hotels could be found for the provided zipcode'})
    return jsonify(hotel_recommendations)


@api_v1.route('/rec_html', methods=['GET'])
@token_required
@use_args(query_args, locations=('query',))
def recommendation_as_html(args):
    set_checkin_and_checkout(args)
    hotel_recommendations = StandardEngine.query(args)
    if not hotel_recommendations:
        return jsonify({'status': 'No hotels could be found for the provided zipcode'})
    formatted_hotels = HotelDataFormatter.format_hotel_data(hotel_recommendations, args)
    hotel_htmls = StandardAdGenerator.generate_ads_as_html(formatted_hotels)
    num = 0
    if args.get('num', 0):
        num = args.get('num') % 4
    return hotel_htmls[num]


@api_v1.route('/rec_image', methods=['GET'])
@token_required
@use_args(query_args, locations=('query',))
def recommendation_as_image(args):
    set_checkin_and_checkout(args)
    if not args.get('context_id', None):
        hotel_recommendations = StandardEngine.query(args)
        if not hotel_recommendations:
            return jsonify({'status': 'No hotels could be found for the provided zipcode'})
        cache_data(hotel_recommendations)
        location_id = hotel_recommendations[0]['cityId']
        context = RecommendationContext(hotels=hotel_recommendations, zipcode=args.get('zipcode'))
    else:
        context = RecommendationContext.from_id(args.get('context_id'))
        location_id = context.hotels[0]['cityId']
    urls = context.generate_urls()
    return render_template('inlined_full_template.html', url_pairs=urls,
                           args=args, location_id=location_id, context_id=context.id)
    # return render_template('inlined_full_template.html', url_pairs=urls,
    #                        args=args, location_id=location_id, context_id=context.id)


@api_v1.route('/rec_email', methods=['GET'])
@token_required
@use_args(query_args, locations=('query',))
def recommendation_as_email(args):
    set_checkin_and_checkout(args)
    hotel_recommendations = StandardEngine.query(args)
    if not hotel_recommendations:
        return jsonify({'status': 'No hotels could be found for the provided zipcode'})
    cache_data(hotel_recommendations)
    location_id = hotel_recommendations[0]['cityId']
    context = RecommendationContext(hotels=hotel_recommendations, zipcode=args.get('zipcode'))
    urls = context.generate_urls()
    print('Sending email...')
    html = render_template('inlined_full_template.html', url_pairs=urls, args=args, location_id=location_id)
    sender = GmailMailer(args.get('email'))
    sender.send_email(html)
    return jsonify({
        'status': 'Email sent to {0}'.format(args.get('email')),
        'context_id': context.id
    })



@api_v1.route('/context_update', methods=['GET'])
@token_required
@use_args(update_args, locations=('query',))
def context_update(args):
    context_id = args.get('context_id')
    context = RecommendationContext.from_id(context_id)
    if not args.get('zipcode', None):
        args['zipcode'] = context.zipcode
    else:
        zipcode = args.get('zipcode')
        context.set_zipcode(zipcode)
    hotel_recommendations = StandardEngine.query(args)
    cache_data(hotel_recommendations)
    if len(hotel_recommendations) < 4:
        return jsonify({'status': 'failed', 'msg': 'Four hotels could not be retrieved with the given params.'}, 400)
    context.set_hotels(hotel_recommendations)
    return jsonify({'status': 'ok', 'msg': 'Ad context was updated with new params.', 'args': args})


@api_v1.route('/dynamic_tag', methods=['GET'])
@token_required
@use_args(img_tag, locations=('query',))
def img_tag_request(args):
    set_checkin_and_checkout(args)
    width, height = args.get('dimensions', '260x360').split('x')
    hotel_recommendations = StandardEngine.query(args)
    if not hotel_recommendations:
        return jsonify({'status': 'No hotels could be found for the provided zipcode'})
    cache_data(hotel_recommendations)
    location_id = hotel_recommendations[0]['cityId']
    context = RecommendationContext(hotels=hotel_recommendations, zipcode=args.get('zipcode'))
    urls = context.generate_urls(args)
    tags = []
    for url in urls:
        tags.append({
            'tag': '<a target="_blank" href={}><img src="{}"></a>'.format(url.data, url.img),
            'urls': {
                'image': url.img,
                'redirect': url.data
            }
        })
    rank = args.get('rank', None)
    if rank:
        return jsonify({
            'status': 'ok',
            'tag': tags[rank - 1],
            'context_id': context.id,
            'total_recommendations': len(hotel_recommendations)
        })
    else:
        return jsonify({
            'status': 'ok',
            'tags': tags,
            'context_id': context.id,
            'total_recommendations': len(hotel_recommendations)
        })

@api_v1.route('/dynamic_tag_html', methods=['GET'])
@token_required
@use_args(img_tag, locations=('query',))
def img_tag_request_html(args):
    set_checkin_and_checkout(args)
    width, height = args.get('dimensions', '260x360').split('x')
    if not args.get('context_id', None):
        hotel_recommendations = StandardEngine.query(args)
        if not hotel_recommendations:
            return jsonify({'status': 'No hotels could be found for the provided zipcode'})
        cache_data(hotel_recommendations)
        location_id = hotel_recommendations[0]['cityId']
        context = RecommendationContext(hotels=hotel_recommendations, zipcode=args.get('zipcode'))
    else:
        context = RecommendationContext.from_id(args.get('context_id'))
        location_id = context.hotels[0]['cityId']
    urls = context.generate_urls(args)
    url = urls[args.get('rank', 1) - 1]
    tag = '<a target="_blank" href={}><img src="{}"></a>'.format(url.data, url.img),
    return tag



def set_checkin_and_checkout(args):
    event_date_str = args.get('event_date', str(date.today()))
    event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
    delta = timedelta(days=5)
    check_in = max(event_date - delta, date.today())
    check_out = max(event_date + delta, check_in + delta)
    args['check_in'] = check_in
    args['check_out'] = check_out


def cache_data(data_list, keyword='hotel'):
    pipe = redis_store.pipeline()
    for data in data_list:
        pipe.hset('cache', '{0}_{1}'.format(keyword, data['id']), json.dumps(data))
    return pipe.execute()
