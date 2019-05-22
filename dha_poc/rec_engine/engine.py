
from dha_poc.data.hotel_api import HotelDataInterface
from dha_poc.data.exceptions import *


hotel_api_interface = HotelDataInterface.get_instance()


class StandardEngine:

    @classmethod
    def query(cls, query_args):
        zipcode = query_args.get('zipcode', None)
        if not zipcode:
            return []
        try:
            hotel_data = hotel_api_interface.get_hotels_by_zipcode(zipcode, query_args)
            hotel_list = hotel_data['hotels']
            if not len(hotel_list):
                return []

            sorted_hotels = StandardSortCriteria.sorted_by_criteria(hotel_list, query_args)
            selected_hotels = sorted_hotels[:6]
            return selected_hotels
        except ZipcodeNotInDatabase:
            # TODO: Log that the zipcode couldn't be found
            pass
        return []


class StandardSortCriteria:

    allowed_criteria = set(['distance', 'popularity', 'rating', 'price'])

    @classmethod
    def sorted_by_criteria(cls, hotel_list, args):
        descending = bool(args.get('descending', True))
        sort_params = args.get('sort_criteria', 'distance,popularity,rating,price')
        sort_criteria = [c for c in sort_params.split(',') if c in StandardSortCriteria.allowed_criteria]
        for criterion in StandardSortCriteria.allowed_criteria:
            if criterion not in sort_criteria:
                sort_criteria.append(criterion)
        price = args.get('price', None)
        rated_hotels = []
        for hotel in hotel_list:
            if 'photos' not in hotel or len(hotel['photos']) == 0:
                continue
            elif 'name' not in hotel:
                continue
            if not price:
                price_dist = hotel.get('priceFrom', 0)
            else:
                price_dist = - (hotel.get('best_price', 10e6) - price) ** 2
            distance = -hotel.get('distance_to_event', 30)
            has_price = int(bool(hotel.get('best_price', False)))
            has_summary = int(bool(hotel.get('summary', False)))
            has_roomtype = int(bool(hotel.get('photosByRoomType', False)))
            criteria_dict = {
                'price': price_dist,
                'popularity': hotel.get('popularity', 0),
                'rating': hotel.get('rating', 0),
                'distance': hotel.get('popularity', 0)
            }
            criteria = [has_price, has_summary, has_roomtype] + [criteria_dict[crit] for crit in sort_criteria]
            rated_hotels.append((hotel, criteria))
        sorted_hotels = sorted(rated_hotels, key=lambda h: h[1], reverse=descending)
        return [h[0] for h in sorted_hotels]
