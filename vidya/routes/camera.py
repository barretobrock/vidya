from datetime import datetime
from pathlib import Path
from typing import (
    List,
    Tuple,
)

from PIL import Image
import cv2
from flask import (
    Blueprint,
    current_app,
    make_response,
    request,
)
import imageio.v3 as iio
import imutils
from loguru import logger
from pygifsicle import optimize

from vidya import ROOT
from vidya.core.camera import IPCamera
from vidya.core.motion_detect import detect_motion
from vidya.core.notify import upload_to_slack

bp_cam = Blueprint('snap', __name__, url_prefix='/cam/<int:cam_id>/')

BASE_PATH = ROOT.joinpath('snaps')


def process_args() -> Tuple[str, str, int]:
    detection_type = request.args.get('detection_type', 'motion')
    detection_time = request.args.get('detection_time')
    take_seconds = request.args.get('take_seconds', '5')
    if detection_time is None or detection_time == '':
        detection_time = datetime.now().strftime('%F %T')
    if take_seconds is None or take_seconds == '':
        take_seconds = 5
    else:
        take_seconds = int(take_seconds)
    return detection_type, detection_time, take_seconds


def build_message(detection_type: str, cam: IPCamera, detection_time: str,
                  cnts: int = None, cnts_per_frame: List[str] = None) -> str:
    msg = f'*`{detection_type.title()}`* detected in `{cam.cam_name}` at `{detection_time}`.'
    if cnts is not None:
        msg += f' *`{cnts}`* contours in frame.'
    elif cnts_per_frame is not None:
        msg += f' *`{sum(cnts_per_frame) / len(cnts_per_frame)}`* avg contours per frame.'
    return msg


def do_base_snapshot(cam_id: int, quality: int = 35, is_optimize: bool = True):
    """Takes a 'base' snapshot -- used for setting baseline for comparing motion"""
    base_img_path = BASE_PATH.joinpath(f'cam_{cam_id}_base.jpg')
    cam = current_app.extensions['cams'][cam_id]  # type: IPCamera

    logger.debug('Taking snapshot...')
    img = cam.snap()

    img.save(base_img_path, quality=quality, optimize=is_optimize)


def do_snapshot(cam_id: int, quality: int = 35, is_optimize: bool = True) -> Tuple[Path, int]:
    """Takes a snapshot. If there's a base image, applies contours as a motion comparison"""
    base_img_path = BASE_PATH.joinpath(f'cam_{cam_id}_base.jpg')
    snap_img_path = BASE_PATH.joinpath(f'cam_{cam_id}_snap.jpg')
    cam = current_app.extensions['cams'][cam_id]  # type: IPCamera

    logger.debug('Taking snapshot...')
    img = cam.snap()

    if base_img_path.exists():
        logger.debug('Reading in past image')
        past_img = Image.open(base_img_path)
        _, bg, _ = detect_motion(past_img, None)
        img, _, ctrs = detect_motion(img, bg)
    else:
        ctrs = 0

    img.save(snap_img_path, quality=quality, optimize=is_optimize)
    return snap_img_path, len(ctrs)


@bp_cam.route('/update-img', methods=['GET'])
def update_base_img(cam_id: int):
    """Updates the 'base' image to serve as comparison against
    the image that's snapped on motion"""
    do_base_snapshot(cam_id)
    return make_response('', 200)


@bp_cam.route('/snap', methods=['GET'])
def snapshot(cam_id: int):
    cam = current_app.extensions['cams'][cam_id]  # type: IPCamera
    detection_type, detection_time, _ = process_args()

    img_path, ctrs = do_snapshot(cam_id)
    upload_to_slack(
        img_path,
        slack_client=current_app.extensions['slack'],
        channel=cam.slack_channel,
        text=build_message(detection_type, cam, detection_time, cnts=ctrs)
    )
    return make_response('', 200)


@bp_cam.route('/gif', methods=['GET'])
def take_gif(cam_id):
    detection_type, detection_time, take_seconds = process_args()
    n_frames = take_seconds * 4  # 4 fps
    logger.info(f'Generating gif of {take_seconds}s ({n_frames} frames)')

    cam = current_app.extensions['cams'][cam_id]  # type: IPCamera
    cap = cam.stream()
    frames = []
    cnts_per_frame = []
    bg = None

    logger.debug('Beginning frame collection')
    for i in range(n_frames):
        _, frame = cap.read()
        if frame.shape[1] > 640:
            frame = imutils.resize(frame, width=640)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb_frame, bg, cnts = detect_motion(rgb_frame, bg)
        # TODO: Capture cnts per frame and put average in slack msg
        cnts_per_frame.append(len(cnts))
        frames.append(rgb_frame)

    cap.release()
    logger.debug('Completed frame collection')

    gif_path = BASE_PATH.joinpath(f'cam_{cam_id}_motion.gif')
    logger.debug('Saving gif...')
    iio.imwrite(gif_path, frames, duration=200, loop=0, quality=1)
    logger.debug('Optimizing gif...')
    optimize(gif_path)

    logger.debug('Uploading gif to Slack...')
    upload_to_slack(
        gif_path,
        slack_client=current_app.extensions['slack'],
        channel=cam.slack_channel,
        text=build_message(detection_type, cam, detection_time, cnts_per_frame=cnts_per_frame)
    )

    return make_response('', 200)
