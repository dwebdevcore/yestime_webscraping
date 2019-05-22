import base64
import os
import json

from selenium import webdriver
from flask import render_template
from dha_poc.start import flask_app, redis_store
from dha_poc.util import zipcode_regex
from dha_poc.url_manager.exceptions import InvalidDataBundleId, AdImageReadException
from dha_poc.data.formatter import HotelDataFormatter
from dha_poc.data.exceptions import HotelNotFoundInCache


class StandardAdGenerator:

    @classmethod
    def generate_ads(cls, hotel_list):
        hotel_images = []
        for hotel in hotel_list:
            hotel_images.append({
                'image': cls.get_ad_image(hotel),
                'hotel': hotel
            })
        return hotel_images

    @classmethod
    def get_ad_image(cls, hotel, args):
        width = int(args.get('width', '260'))
        height = int(args.get('height', '360'))
        checkin = args.get('checkin', None)
        checkout = args.get('checkout', None)
        if not (238 < width < 650 and 290 < height < 700):
            width, height = 260, 370
        headless_browser = webdriver.PhantomJS()
        html = render_template('hotel_block.html', hotel=hotel, checkin=checkin, checkout=checkout)
        headless_browser.get(html)
        size = headless_browser.find_element_by_id('hotel-block').size
        headless_browser.set_window_size(width, height)
        img = headless_browser.get_screenshot_as_png()
        headless_browser.quit()
        return img

    @classmethod
    def generate_ads_as_html(cls, hotel_list):
        hotels_html = []
        checkin = '2017-06-17'
        checkout = '2017-06-22'
        for hotel in hotel_list:
            hotels_html.append(render_template('hotel_block.html', hotel=hotel, checkin=checkin, checkout=checkout))
        return hotels_html


class AdDataBundle:

    def __init__(self, image_data, args):
        self._img = image_data.get('image')
        self.hotel = image_data.get('hotel')
        self.zipcode = args.get('zipcode')
        self.hotel_id = self.hotel.get('id')
        self.bundle_id = self.get_encoded_bundle_identifier()
        self.img_filename = AdDataBundle._build_filename(self.bundle_id)

    @property
    def img(self):
        if self._img:
            return self._img
        binary = None
        try:
            with (self.img_filename, 'rb') as f:
                binary = f.read()
        except Exception as e:
            raise AdImageReadException(e)
        return binary

    @img.setter
    def img(self, val):
        self._img = val

    @classmethod
    def _build_filename(cls, id):
        return os.path.join(flask_app.config['AD_IMAGES_DIR'], '{0}.png'.format(id))

    @classmethod
    def from_identifier(cls, id):
        data_str = base64.urlsafe_b64decode(id.encode('utf8')).decode('utf8')
        params = data_str.split('|')
        if len(params) <= 1:
            raise InvalidDataBundleId('The provided id doesn\'t create enough params.')
        elif not zipcode_regex.match(params[0]):
            raise InvalidDataBundleId('The zipcode extracted from id is not valid.')

        filename = cls._build_filename(id)
        zipcode, hotel_id = params
        hotel = redis_store.hget('cache', 'hotel_{0}'.format(hotel_id))
        if hotel:
            hotel = json.loads(hotel.decode('utf8'))
            formatted_hotel = HotelDataFormatter.format_hotel(hotel)
            image_data = {'hotel': formatted_hotel, 'image': None}
            return cls(image_data, {'zipcode': zipcode})
        else:
            raise HotelNotFoundInCache('Hotel with id: {0} was not found in redis cache.'.format(hotel_id))

    def get_encoded_bundle_identifier(self):
        params = []
        params.append(str(self.zipcode))
        params.append(str(self.hotel_id))
        data_str = '|'.join(params)
        return base64.urlsafe_b64encode(data_str.encode('utf8')).decode('utf8')
