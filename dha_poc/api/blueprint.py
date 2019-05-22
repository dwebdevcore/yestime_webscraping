from flask import Blueprint


api_v1 = Blueprint(
    'api_v1',
    __name__,
    template_folder='templates'
)
