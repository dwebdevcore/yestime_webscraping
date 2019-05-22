import os
import requests
import gzip
import json

from random import sample
from geopy.distance import vincenty as geoc_distance
from subprocess import call
from furl import furl
from collections import defaultdict
from requests_futures.sessions import FuturesSession
from dha_poc.start import redis_store, flask_app
from dha_poc.data.exceptions import ZipcodeNotInDatabase, HTTPRequestFailedException
from dha_poc.util import generate_hotel_price_url


def load_zipcodes(zipcode_file=flask_app.config['ZIPCODE_FILE']):
    city_zipcodes = defaultdict(lambda: set())
    zipcode_to_city = defaultdict(lambda: None)
    with open(zipcode_file, 'r') as f:
        headers = [h.lower().replace(' ', '_') for h in f.readline().split(',')]
        for line in f.readlines():
            data = dict(zip(headers, line.lower().split(',')))
            city_zipcodes[data['place_name']].add(data['postal_code'])
            zipcode_to_city[data['postal_code']] = data['place_name']
    return city_zipcodes, zipcode_to_city


def load_hotel_list(req=requests, hotel_tmp_file=flask_app.config['HOTEL_TMP_FILENAME']):
    hotels_by_location = defaultdict(lambda: [])
    file_already_exists_and_is_valid = os.path.isfile(hotel_tmp_file) and call(['gzip', '-t', hotel_tmp_file]) == 0
    if not file_already_exists_and_is_valid:
        # TODO: Handle the case where this request doesn't work
        print('>>> Downloading hotel list')
        r = req.get(flask_app.config['HOTEL_LIST_URL'], stream=True)
        with open(hotel_tmp_file, 'wb') as f:
            for chunk in r.iter_content(chunk_size=128):
                f.write(chunk)

    with gzip.open(hotel_tmp_file, 'rb') as f:
        print('>>> Uncompressing hotel list')
        # id,name,location_name,location_id,location_iata,country_name,photos_count
        headers = f.readline().decode('utf8').strip().split(',')
        for line in f.readlines():
            row = line.decode('utf8').strip()
            data = dict(zip(headers, row.split(',')))
            if data['country_name'] != 'United States':
                continue
            hotels_by_location[data['location_name'].lower()].append({
                'name': data['name'],
                'location_id': data['location_id']
            })
    return hotels_by_location


def load_zipcode_to_location():
    _, zipcode_to_city = load_zipcodes()
    hotels_by_location = load_hotel_list()
    return build_zipcode_to_location_map(zipcode_to_city, hotels_by_location)


def build_zipcode_to_location_map(zipcode_to_city, hotels_by_location):
    zipcode_to_location = {}
    for zipcode, city in zipcode_to_city.items():
        if city in hotels_by_location and zipcode not in zipcode_to_location:
            hotel_info = hotels_by_location[city][0]
            zipcode_to_location[zipcode] = hotel_info['location_id']
    return zipcode_to_location


def save_hash_to_db(zipcode_to_location, db=redis_store):
    pipe = db.pipeline()
    print('>>> Updating zipcode to location DB in Redis')
    for zipcode, location in zipcode_to_location.items():
        pipe.hset('zc_to_loc_hash', zipcode, location)
    pipe.set('hotel_list_is_up_to_date', 1, ex=flask_app.config['HOTEL_LIST_EXPIRE_TIME'])
    return pipe.execute()


def build_zipcode_to_geoc_data(db=redis_store):
    with open(flask_app.config['ZIPCODE_TO_GEOC_FILE'], 'r') as f:
        pipe = db.pipeline()
        header = f.readline().lower().split(',')  # skip header
        for line in f.readlines():
            row = dict(zip(header, line.split(',')))
            pipe.hset('zipcode_to_geoc_map', row['postal code'].strip(),
                      '{0},{1}'.format(row['latitude'].strip(), row['longitude'].strip()))
        return pipe.execute()


class HotelDataInterface:

    instance = None

    def __init__(self, redis_instance=redis_store, request_lib=requests):
        self.db = redis_instance
        self.req = request_lib

        # Loads hotel list, creates zipcode to location hash and stores it in Redis
        if self.db.hlen('zipcode_to_geoc_map') == 0:
            build_zipcode_to_geoc_data(self.db)

    @classmethod
    def get_instance(cls):
        if not cls.instance:
            cls.instance = HotelDataInterface()
        return cls.instance

    def _get_location_hotels(self, location):
        data = self.db.hget('location_to_hotel_list', location)
        if data:
            return json.loads(data.decode('utf8'))
        return None

    def _set_location_hotels(self, location, data):
        return self.db.hset('location_to_hotel_list', location, json.dumps(data))

    def _get_locations_from_zc(self, zipcode):
        coord = self.db.hget('zipcode_to_geoc_map', zipcode).decode('utf8')
        url = flask_app.config['HOTELS_BY_COORDINATE_URL_TEMPLATE'].format(coord)
        r = requests.get(url)
        if r.status_code == 200:
            data = r.json()
            r.close()
            if data.get('status', None) != 'ok':
                return None
            hotels = data.get('results', {}).get('hotels', [])
            locations = set()
            for hotel in hotels:
                if 'locationId' in hotel:
                    locations.add(hotel['locationId'])
            return locations
        return None

    def get_hotels_by_zipcode(self, zipcode, args={}):
        query_params = '|'.join([ str(p[1]) for p in list(args.items()) if p[0] != 'num'])
        if self.db.hexists('cache', 'api_{0}'.format(zipcode)):
            return json.loads(self.db.hget('cache', 'api_{0}'.format(zipcode)).decode('utf8'))
        locations = self._get_locations_from_zc(zipcode)
        if not len(locations):
            raise ZipcodeNotInDatabase()
        if len(locations) > 10:
            locations = sample(locations, 10)
        print('Zipcode {0} matches with locations: {1}'.format(zipcode, str(locations)))
        hotel_obj = self.get_hotels_from_locations(locations)
        valid_hotels = self._attach_additional_data(hotel_obj['hotels'], args)
        hotels = {'hotels': valid_hotels}
        self.db.hset('cache', 'api_{0}'.format(zipcode), json.dumps(hotels))
        return hotels

    def _attach_additional_data(self, hotels, args={}):
        city_ids = set()
        check_in = args.get('check_in')
        check_out = args.get('check_out')
        event_coord = self.db.hget('zipcode_to_geoc_map', args.get('zipcode')) \
            .decode('utf8').split(',')
        urls = []
        nearby_hotels = []
        for hotel in hotels:
            hotel_coord = hotel['location']['lat'], hotel['location']['lon']
            hotel['distance_to_event'] = geoc_distance(event_coord, hotel_coord).miles
            if hotel['distance_to_event'] <= 30:
                nearby_hotels.append(hotel)
                if 'cityId' in hotel:
                    city_ids.add(hotel['cityId'])
        if len(city_ids) > 10:
            city_ids = sample(city_ids, 10)
        if len(nearby_hotels) > 300:
            nearby_hotels = sample(nearby_hotels, 300)
        for city_id in city_ids:
            urls.append(generate_hotel_price_url(
                city_id, str(check_in), str(check_out),
                args.get('currency', 'usd'), args.get('language', 'en')))
        responses = []
        futures = []
        hotel_additional_data = {}
        print('Fetching cityIds: {0}'.format(city_ids))
        with FuturesSession(max_workers=len(urls)) as session:
            for url in urls:
                futures.append(session.get(url))
            for future in futures:
                res = future.result()
                if res.status_code != 200:
                    continue
                responses.append(res.json())
            for res in responses:
                if 'tophotels' not in res:
                    continue
                for hotel in res['tophotels']:
                    if hotel['hotel_id'] in hotel_additional_data:
                        continue
                    hotel_additional_data[hotel['hotel_id']] = {
                        'price_per_night': hotel.get('last_price_info').get('price_pn', 0) if hotel['last_price_info'] else 0,
                        'summary': hotel.get('ty_summary', None)
                    }
        for hotel in nearby_hotels:
            hotel['language'] = args.get('language', 'en')
            hotel['currency'] = args.get('currency', 'usd')
            if hotel['id'] in hotel_additional_data:
                hotel.update(hotel_additional_data[hotel['id']])
            price_from = hotel.get('pricefrom', 0)
            price_per_night = hotel.get('price_per_night', 0)
            if price_from > 0 and price_per_night > 0:
                hotel['best_price'] = min(price_from, price_per_night)
                hotel['worst_price'] = max(price_from, price_per_night)
            elif price_from > 0 and price_per_night == 0:
                hotel['best_price'] = price_from
            elif price_from == 0 and price_per_night > 0:
                hotel['best_price'] = price_per_night
        return nearby_hotels

    def get_hotels_from_locations(self, locations):
        urls = []
        url_builder = furl(flask_app.config['HOTEL_BY_LOCATION_URL'])
        for location in locations:
            url_builder.args['token'] = flask_app.config['HOTEL_DATA_API_TOKEN']
            url_builder.args['locationId'] = location
            urls.append(url_builder.url)
        hotels = {}
        futures = []
        with FuturesSession(max_workers=len(locations)) as session:
            for url in urls:
                futures.append(session.get(url))
            for future in futures:
                res = future.result()
                if res.status_code != 200:
                    continue
                data = res.json()
                for hotel in data.get('hotels', []):
                    if 'id'  in hotel:
                        hotels[hotel['id']] = hotel
        return {'hotels': list(hotels.values())}
