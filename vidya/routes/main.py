from flask import (
    Blueprint,
    make_response,
)

from vidya import __version__

bp_main = Blueprint('main', __name__)


@bp_main.route('/', methods=['GET'])
def main_page():
    return make_response({
        'success': True,
        'payload': {
            'version': __version__
        }
    }, 200)
