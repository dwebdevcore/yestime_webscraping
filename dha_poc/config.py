import os

ENVIRONTMENT = os.environ.get('ENVIRONMENT', 'PRODUCTION')
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEDIA_DIR = os.path.join(ROOT_DIR, 'media')


class DefaultConfig:
    ENVIRONTMENT = ENVIRONTMENT
    ROOT_DIR = ROOT_DIR
    BASE_DIR = BASE_DIR
    MEDIA_DIR = MEDIA_DIR
    AD_IMAGES_DIR = os.path.join(MEDIA_DIR, 'ad_images')

    ZIPCODE_FILE = os.path.join(BASE_DIR, 'us_postal_codes.csv')
    ZIPCODE_TO_GEOC_FILE = os.path.join(BASE_DIR, 'us_postal_codes.csv')

    HOTEL_SITE_REDIRECT_URL_TEMPLATE = "https://search.hotellook.com/?hotelId={hotel_id}&locationId={location_id}&adults=2&language={hotel_lang}&currency={hotel_currency}&_ga=2.149165750.1817712291.1495153264-1549267885.1495153264&marker=136741"
    HOTEL_PRICE_DATA_URL_TEMPLATE = 'http://yasen.hotellook.com/tp/public/widget_location_dump.json?currency={0}&language={1}&limit=20&id={2}&type=tophotels&check_in={3}&check_out={4}&token={5}'
    HOTELS_BY_COORDINATE_URL_TEMPLATE = 'http://engine.hotellook.com/api/v2/lookup.json?query={0}&lang=en&lookFor=hotel&limit=10'
    HOTEL_PHOTO_URL_TEMPLATE = 'http://photo.hotellook.com/rooms/{5}/h{0}_{1}_{2}/{3}/{4}.auto'
    HOTEL_LIST_URL = 'http://yasen.hotellook.com/tp/v1/hotels?language=en'
    HOTEL_TMP_FILENAME = '/tmp/hotel_list.csv.gz'
    HOTEL_BY_LOCATION_URL = 'http://engine.hotellook.com/api/v2/static/hotels.json'
    HOTEL_DATA_API_TOKEN = os.environ.get('HOTEL_DATA_API_TOKEN', 'token')
    HOTEL_LIST_EXPIRE_TIME = 60 * 60 * 48


    PARKING_SITE_REDIRECT_URL_TEMPLATE = "https://search.hotellook.com/?hotelId={hotel_id}&locationId={location_id}&adults=2&language={hotel_lang}&currency={hotel_currency}&_ga=2.149165750.1817712291.1495153264-1549267885.1495153264&marker=136741"
    PARKING_TMP_FILENAME = '/tmp/hotel_list.csv.gz'
    PARKING_SEARCH_SURL = 'https://www.way.com/way-service/parking/search'
    #PARKING_DATA_API_TOKEN = os.environ.get('HOTEL_DATA_API_TOKEN', 'token')
    PARKING_LIST_EXPIRE_TIME = 60 * 60 * 48

    API_URL_PREFIX = '/api/v1'
    IMG_URL_PREFIX = '/img/v1'
    DATA_URL_PREFIX = '/data/v1'

    IMG_FILE_EXTENSION = 'png'
    
    GMAIL_USER_ADDRESS = 'yestime.poc@gmail.com'
    GMAIL_USER_PASSWORD = 'helloworld'
    GMAIL_SMTP_ADDRESS = 'smtp.gmail.com'
    GMAIL_SMTP_PORT = '587'

    ID_ENCRYPTION_KEY = b'LocS5mCfw-P_qdzgOd9-xq5eRPHU34E_c9Epe5dSbOA='
    
if DefaultConfig.ENVIRONTMENT == 'DEBUG':
    class Config(DefaultConfig):
        TOKEN = 'secret'
        SECRET_KEY = 'a_secret_debug_key'
        DEBUG = True
        REDIS_URL = 'redis://redisdb.yesti.me:6379/0'
        TEST_STATIC_FILES_DIR = os.path.join(DefaultConfig.ROOT_DIR, os.path.join('test', 'static'))
        HOSTNAME = '127.0.0.1'
        PROTOCOL = 'http'
        PORT = 5555

elif DefaultConfig.ENVIRONTMENT == 'PRODUCTION':
    class Config(DefaultConfig):
        TOKEN = os.environ['API_DEFAULT_TOKEN']
        SECRET_KEY = os.environ['FLASK_SECRET_KEY']
        DEBUG = False
        REDIS_URL = "redis://:{0}@redisdb.yesti.me:{1}/0".format(
            os.environ.get('REDIS_PASSWORD'),
            os.environ.get('REDIS_PORT')
        )
        HOSTNAME = 'yesti.me'
        PROTOCOL = 'http'
