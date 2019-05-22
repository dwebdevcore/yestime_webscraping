import json
import re
import random
import datetime

from dha_poc.util import generate_prefixed_url
from dha_poc.start import flask_app, redis_store
from dha_poc.url_manager.exceptions import HotelNotFoundInCache
from dha_poc.data.formatter import HotelDataFormatter
from dha_poc.ads_creator.creator import AdDataBundle, StandardAdGenerator
from dha_poc.url_manager.exceptions import NoZipcodeAsignedToContext
from cryptography.fernet import Fernet
from collections import namedtuple

crypto_suite = Fernet(flask_app.config['ID_ENCRYPTION_KEY'])
UrlPair = namedtuple('Strings', ['img', 'data'])


class ImageURLManager:

    @classmethod
    def store_img(cls, data_bundle):
        with open(data_bundle.img_filename, 'wb') as f:
            f.write(data_bundle.img)

    @classmethod
    def generate_url(cls, data_bundle):
        id = data_bundle.bundle_id
        if flask_app.config['PORT']:
            return '{0}://{1}:{2}{3}/{4}'.format(
                flask_app.config['PROTOCOL'],
                flask_app.config['HOSTNAME'],
                flask_app.config['PORT'],
                flask_app.config['IMG_URL_PREFIX'],
                id
            )
        else:
            return '{0}://{1}{2}/{3}'.format(
                flask_app.config['PROTOCOL'],
                flask_app.config['HOSTNAME'],
                flask_app.config['IMG_URL_PREFIX'],
                id
            )

    @classmethod
    def process_ad(cls, data_bundle):
        cls.store_img(data_bundle)
        url = cls.generate_url(data_bundle)
        return url


class RecommendationContext:

    def __init__(self, hotels=None, id=None, zipcode=None, db=redis_store):
        self.db = db
        self.id = id if id else self.create_id()
        self.hotels = self.prepare_hotels(hotels)
        self.set_zipcode(zipcode)


    @classmethod
    def from_id(cls, id):
        return RecommendationContext(id=id, db=redis_store)

    def set_zipcode(self, zipcode):
        if not zipcode:
            zipcode = self.db.hget('rec_context_zipcodes', self.id)
            if not zipcode:
                raise NoZipcodeAsignedToContext('Could not find zipcode {}'.format(zipcode))
            self.zipcode = zipcode.decode('utf8')
        else:
            self.zipcode = zipcode
            self.db.hset('rec_context_zipcodes', self.id, zipcode)

    @classmethod
    def from_encrypted_id(cls, encrypted_id):
        id = RecommendationContext.decrypted_id(encrypted_id)
        return RecommendationContext.from_id(id)

    def generate_urls(self, args={}):
        encrypted_id = self.encrypted_id()
        urls = []
        width, height = args.get('dimensions', '600x595').split('x')
        today = datetime.datetime.today()
        after_today = today + datetime.timedelta(days=7)
        checkin = args.get('check_in', today.strftime("%Y-%M-%d"))
        checkout = args.get('check_out', after_today.strftime("%Y-%M-%d"))
        for num in range(4):
            template_img = generate_prefixed_url(flask_app.config['IMG_URL_PREFIX'])
            template_data = generate_prefixed_url(flask_app.config['DATA_URL_PREFIX'])
            urls.append(UrlPair(
                template_img + '/{}/{}'.format(encrypted_id, num) +\
                    '?width={}&height={}&checkin={}&checkout={}'.format(width, height, checkin, checkout),
                template_data + '/{}/{}'.format(encrypted_id, num)
            ))
        return urls

    def encrypted_id(self):
        return crypto_suite.encrypt(str(self.id).encode('ascii')).decode('utf8')

    @classmethod
    def decrypted_id(self, encrypted_id):
        binary_cipher = encrypted_id.encode('ascii')
        decrypted = crypto_suite.decrypt(binary_cipher).decode('ascii')
        num = re.sub(r'[^\d]', '', decrypted)
        return int(num)

    def create_id(self):
        pipe = self.db.pipeline()
        pipe.incr('rec_context_id_generator')
        pipe.get('rec_context_id_generator')
        result = pipe.execute()
        return int(result[1].decode('ascii'))

    def set_hotels(self, hotels):
        self.hotels = self.prepare_hotels(hotels)
        free_hotels = self.db.smembers('rec_context_hotels_{}'.format(self.id))
        pipe = self.db.pipeline()
        pipe.delete(self.get_free_hotels_id())
        pipe.sadd(self.get_free_hotels_id(), *free_hotels)
        for i in range(4):
            id = 'ad_{}_{}'.format(self.id, i)
            if self.db.exists(id):
                pipe.delete(id)
        pipe.execute()

    def prepare_hotels(self, hotels):
        if not hotels:
            hotel_ids_set = self.db.smembers('rec_context_hotels_{0}'.format(self.id))
            hotel_ids = [hid.decode('ascii') for hid in hotel_ids_set]
            pipe = self.db.pipeline()
            for hotel_id in hotel_ids:
                pipe.hget('cache', 'hotel_{0}'.format(hotel_id))
            raw_hotels = pipe.execute()
            hotels = []
            for i, hotel in enumerate(raw_hotels):
                if not hotel:
                    raise HotelNotFoundInCache('Could not find hotel with id {0}'.format(hotel_id[i]))
                else:
                    hotels.append(json.loads(hotel.decode('utf8')))
        else:
            hotel_ids = [h['id'] for h in hotels]
            hotel_set_id = 'rec_context_hotels_{0}'.format(self.id)
            if self.db.exists(hotel_set_id):
                self.db.delete(hotel_set_id)
            self.db.sadd(hotel_set_id, *hotel_ids)
        return hotels

    def get_free_hotels_id(self):
        if not getattr(self, 'free_hotels_id', None):
            self.free_hotels_id = 'free_hotels_{}'.format(self.id)
        return self.free_hotels_id

    def get_ad(self, num, args):
        if not 0 <= num <= 3:
            return None
        hotel_id = self.db.get('ad_{}_{}'.format(self.id, num))
        if not hotel_id and not self.db.exists(self.get_free_hotels_id()):
            free_hotels = self.db.smembers('rec_context_hotels_{}'.format(self.id))
            self.db.sadd(self.get_free_hotels_id(), *free_hotels)
            new_hotel_id = self.db.spop(self.get_free_hotels_id())
        elif not hotel_id:
            new_hotel_id = self.db.spop(self.get_free_hotels_id())
        else:
            self.db.sadd(self.get_free_hotels_id(), hotel_id)
            new_hotel_id = self.db.spop(self.get_free_hotels_id())
        new_hotel_id = new_hotel_id.decode('utf8')
        self.db.set('ad_{}_{}'.format(self.id, num), new_hotel_id)
        hotel = self.db.hget('cache', 'hotel_{}'.format(new_hotel_id))
        if not hotel:
            return None
        hotel = json.loads(hotel.decode('utf8'))
        formatted_hotel = HotelDataFormatter.format_hotel(hotel)
        self.change_hotel_data(formatted_hotel)
        ad_image = StandardAdGenerator.get_ad_image(formatted_hotel, args)
        return ad_image

    def get_hotel(self, num):
        if not 0 <= num <= 3:
            return None
        hotel_id = self.db.get('ad_{}_{}'.format(self.id, num))
        if not hotel_id:
            return None
        hotel_id = hotel_id.decode('utf8')
        hotel = self.db.hget('cache', 'hotel_{}'.format(hotel_id))
        if not hotel:
            return None
        return json.loads(hotel.decode('utf8'))

    def change_hotel_data(self, formatted_hotel):
        hotel = formatted_hotel
        if random.random() >= .8:
            if hotel.get('worst_price', None):
                return
            elif hotel.get('best_price', None):
                hotel['worst_price'] = hotel.get('best_price')
                discount_perc = 1.0 / (5 * (random.randint(5, 31) % 5 + 1))
                hotel['best_price'] = hotel.get('best_price') * (1 - discount_perc)

