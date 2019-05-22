import os

from unittest import mock
from os.path import join
from mockredis import mock_redis_client
from dha_poc.start import redis_store
from dha_poc.app import flask_app
from dha_poc.test.standard_test import StandardTest
from dha_poc.data.hotel_api import *


class HotelDataInterfaceTest(StandardTest):

    def setUp(self):
        self.redis_client = mock_redis_client(host='0.0.0.0', port=6379, db=0)

    def test_load_zipcodes_from_csv_file(self):
        filename = join(flask_app.config['TEST_STATIC_FILES_DIR'], 'test_us_postal_codes.csv')
        city_zipcodes, zipcode_to_city = load_zipcodes(filename)
        zipcodes = [
            '00210', '00211', '00212', '00213', '00214', '00215',
            '00401', '00501', '00544', '01001', '01002', '01003',
            '01004', '01005'
        ]
        cities = [
            ('portsmouth', '00214'),
            ('pleasantville', '00401'),
            ('holtsville', '00544'),
            ('amherst', '01002'),
        ]
        for zc in zipcodes:
            self.assertTrue(zc in zipcode_to_city)
        for city, zc in cities:
            self.assertTrue(city in city_zipcodes)
            self.assertTrue(zc in city_zipcodes[city])

    def test_load_hotel_list(self):
        filename = join(flask_app.config['TEST_STATIC_FILES_DIR'], 'hotels.csv.gz')
        hotels_by_location = load_hotel_list(None, hotel_tmp_file=filename)
        self.assertIn('angel fire', hotels_by_location)
        self.assertIn('hackettstown', hotels_by_location)
        self.assertIn('locust grove', hotels_by_location)
        self.assertIn('ybel', hotels_by_location)
        self.assertEqual(hotels_by_location['angel fire'][0]['location_id'], '20544')
        self.assertEqual(hotels_by_location['hackettstown'][0]['location_id'], '20408')
        self.assertEqual(hotels_by_location['locust grove'][0]['location_id'], '21220')
        self.assertEqual(hotels_by_location['ybel'][0]['location_id'], '1526529')

    def test_save_hash_to_db(self):
        zipcode_to_location = {'44777': '12121212', '00143': '123456'}
        save_hash_to_db(zipcode_to_location, self.redis_client)
        self.assertEqual(self.redis_client.hget('zc_to_loc_hash', '44777'), b'12121212')
        self.assertEqual(self.redis_client.hget('zc_to_loc_hash', '00143'), b'123456')
        self.assertEqual(self.redis_client.get('hotel_list_is_up_to_date'), b'1')

    def test_hotel_interface_hotels_by_location(self):
        location = '1527130'
        sample_resp_filename = join(flask_app.config['TEST_STATIC_FILES_DIR'], 'hotel_by_location_resp.json')
        self.redis_client.incr('hotel_list_is_up_to_date')
        with open(sample_resp_filename, 'r') as f:
            json_resp = f.read()
            response_mock = mock.Mock()
            response_mock.status_code = 200
            response_mock.json = lambda: json.loads(json_resp)
            request_mock = mock.Mock()
            request_mock.get = mock.MagicMock(return_value=response_mock)
            api_interface = HotelDataInterface(redis_instance=self.redis_client, request_lib=request_mock)
            hotel_list = api_interface.get_hotels_by_location(location)
            self.assertDictEqual(hotel_list, json.loads(json_resp))
            self.assertEqual(self.redis_client.hexists('location_to_hotel_list', location), True)
            self.assertDictEqual(api_interface._get_location_hotels(location), hotel_list)
