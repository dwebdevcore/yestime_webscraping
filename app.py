from dha_poc.start import flask_app
from dha_poc.api.blueprint import api_v1
from dha_poc.url_manager.blueprint import img_url_manager_v1, data_url_manager_v1
from dha_poc.api.controllers import *
from dha_poc.url_manager.controllers import *

flask_app.register_blueprint(api_v1, url_prefix=flask_app.config['API_URL_PREFIX'])
flask_app.register_blueprint(img_url_manager_v1, url_prefix=flask_app.config['IMG_URL_PREFIX'])
flask_app.register_blueprint(data_url_manager_v1, url_prefix=flask_app.config['DATA_URL_PREFIX'])

if __name__ == '__main__':
    flask_app.run(
        host=flask_app.config['HOSTNAME'],
        port=flask_app.config['PORT'],
        debug=True,
        threaded=True
    )
