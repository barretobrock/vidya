from flask import (
    Blueprint,
    make_response,
)
from loguru import logger

from vidya import ROOT
from vidya.routes.helpers import (
    get_celery,
    process_args,
)

bp_cam = Blueprint('snap', __name__, url_prefix='/cam/<int:cam_id>/')

BASE_PATH = ROOT.joinpath('snaps')

TASK_NAME_SNAPSHOT = 'vidya.celery_tasks.take_snapshot'
TASK_NAME_GIF = 'vidya.celery_tasks.take_gif'


@bp_cam.route('/snap', methods=['GET'])
def snapshot(cam_id: int):
    detection_type, detection_time, _, quality, _ = process_args()

    payload = dict(
        cam_id=cam_id,
        detection_type=detection_type,
        detection_time=detection_time,
        quality=quality,
        is_optimize=True
    )

    celery_app = get_celery()
    logger.info('Sending task to queue...')
    celery_app.send_task(
        TASK_NAME_SNAPSHOT,
        kwargs=payload
    )

    return make_response({
        'success': True,
        'payload': payload
    }, 200)


@bp_cam.route('/gif', methods=['GET'])
def take_gif(cam_id):
    detection_type, detection_time, take_seconds, quality, fps = process_args()

    payload = dict(
        cam_id=cam_id,
        detection_type=detection_type,
        detection_time=detection_time,
        take_seconds=take_seconds,
        quality=quality,
        fps=fps
    )

    celery_app = get_celery()
    logger.info('Sending task to queue...')
    celery_app.send_task(
        TASK_NAME_GIF,
        kwargs=payload
    )

    return make_response({
        'success': True,
        'payload': payload
    }, 200)
