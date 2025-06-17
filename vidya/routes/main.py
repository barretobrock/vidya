from flask import (
    Blueprint,
    make_response,
)

bp_main = Blueprint('main', __name__)


@bp_main.route('/', methods=['GET'])
def main_page():
    return make_response('OK', 200)
