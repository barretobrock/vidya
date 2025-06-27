from datetime import datetime
import time
from typing import (
    List,
    Tuple,
)

from celery import Celery
from flask import (
    current_app,
    g,
    redirect,
    request,
)
from loguru import logger
from slack_sdk.web import WebClient

from vidya.core.camera import IPCamera


def build_motion_message(detection_type: str, cam: IPCamera, detection_time: str,
                         cnts: int = None, avg_cnts_per_frame: float = None) -> str:
    msg = f'*`{detection_type.title()}`* detected in `{cam.cam_name}` at `{detection_time}`.'
    if cnts is not None:
        msg += f' *`{cnts}`* contours in frame.'
    elif avg_cnts_per_frame is not None:
        msg += f' *`{avg_cnts_per_frame:.1f}`* avg contours per frame.'
    return msg


def get_cam(cam_id: int) -> IPCamera:
    return current_app.extensions['cams'][cam_id]  # type: IPCamera


def get_slack_client() -> WebClient:
    return current_app.extensions['slack']


def get_celery() -> Celery:
    return current_app.extensions['celery']


def process_args() -> Tuple[str, str, int, int, int]:
    detection_type = request.args.get('detection_type', 'motion')
    detection_time = request.args.get('detection_time')
    take_seconds = request.args.get('take_seconds', '5')
    quality = request.args.get('quality', '35')
    fps = request.args.get('fps', '10')

    if detection_time is None or detection_time == '':
        detection_time = datetime.now().strftime('%F %T')
    if take_seconds is None or take_seconds == '':
        take_seconds = 5
    else:
        take_seconds = int(take_seconds)

    if quality is None or quality == '':
        quality = 35
    else:
        quality = int(quality)

    if fps is None or fps == '':
        fps = 10
    else:
        fps = int(fps)

    return detection_type, detection_time, take_seconds, quality, fps


def log_before():
    g.start_time = time.perf_counter()


def log_after(response):
    total_time = time.perf_counter() - g.start_time
    time_ms = int(total_time * 1000)
    logger.info(f'Timing: {time_ms}ms [{request.method}] -> {request.path}')
    return response


def clear_trailing_slash():
    req_path = request.path
    if req_path != '/' and req_path.endswith('/'):
        return redirect(req_path[:-1])


def get_obj_attr_or_default(obj, attrs: List[str], default: str, layout: str = None):
    if obj is None:
        return default
    if layout is None:
        return ','.join([getattr(obj, attr) for attr in attrs])
    else:
        return layout.format(*[getattr(obj, attr) for attr in attrs])
