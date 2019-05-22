from flask import Blueprint


img_url_manager_v1 = Blueprint(
    'img_url_manager_v1',
    __name__,
    template_folder='templates'
)
data_url_manager_v1 = Blueprint(
    'data_url_manager_v1',
    __name__,
    template_folder='templates'
)
