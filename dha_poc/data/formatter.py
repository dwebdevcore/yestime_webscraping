from random import sample, shuffle
from dha_poc.data.hotel_attributes import room_types_per_lang
from dha_poc.start import redis_store
from dha_poc.util import generate_photo_url
from geopy.distance import vincenty as geoc_dist


class HotelDataFormatter:

    @classmethod
    def format_hotel_data(cls, hotels, args):
        formatted_hotels = []
        zipcode = args.get('zipcode')
        for hotel in hotels:
            fields = cls.format_hotel(hotel)
            formatted_hotels.append(fields)
        return formatted_hotels

    @classmethod
    def format_hotel(cls, hotel):
        lang = hotel.get('language', 'en')
        name = hotel.get('name')
        fields = {
            'id': hotel.get('id'),
            'name': name.get(lang, name.get('en'))[:35],
            'stars': hotel.get('stars', 0),
            'rating': hotel.get('rating', 0),
            'popularity': hotel.get('popularity', 0),
            'price_from': hotel.get('priceFrom', 0),
            'photos': cls._get_photo_list(hotel),
            'distance_to_event': hotel.get('distance_to_event'),
            'best_price': hotel.get('best_price', None),
            'worst_price': hotel.get('worst_price', None),
            'summary': hotel.get('summary', ''),
            'locationId': hotel.get('cityId', None),
            'language': lang,
            'currency': hotel.get('currency', 'usd'),
        }
        fields['hotel_type'] = room_types_per_lang[lang][str(hotel.get('propertyType', 1))]
        return fields

    @classmethod
    def _get_photo_list(cls, hotel):
        photos_list = []
        hotel_id = hotel.get('id')
        photos_by_room = hotel.get('photosByRoomType', None)
        if not photos_by_room:
            photos_list = [p['url'] for p in hotel.get('photos')[:4]]
        else:
            room_types = []
            for room_type, qty in photos_by_room.items():
                if len(room_types) >= 4:
                    break
                for i in range(qty):
                    room_types.append((room_type, i))
            for group_id, photo_num in room_types[:4]:
                photos_list.append(generate_photo_url(
                    hotel_id, group_id, photo_num, 640, 480, crop=True))
            if len(photos_list) < 4:
                photos_list += [p['url'] for p in hotel.get('photos')[:4 - len(photos_list)]]
        shuffle(photos_list)
        photos_list[0] = photos_list[0][:-12] + '400/312.auto'
        for i in range(1, len(photos_list)):
            photos_list[i] = photos_list[i][:-12] + '145/95.auto'
        return photos_list
