import os
from typing import List  # noqa: F401

from PIL import Image
from celery import Celery  # noqa: F401
from celery.result import AsyncResult  # noqa: F401
from celery.worker.request import Request  # noqa: F401
import cv2
import imutils
from loguru import logger
import numpy as np

from vidya import ROOT
from vidya.app import create_app
from vidya.core.motion_detect import detect_motion_with_diff
from vidya.core.notify import upload_to_slack
from vidya.routes.helpers import (
    build_motion_message,
    get_cam,
    get_slack_client,
)

BASE_PATH = ROOT.joinpath('snaps')
app = create_app()
celery_app = app.extensions['celery']  # type: Celery


@celery_app.task
def take_snapshot(cam_id: id, detection_type: str, detection_time: str, quality: int = 35,
                  is_optimize: bool = True):
    cam = get_cam(cam_id)

    snap_img_path = BASE_PATH.joinpath(f'cam_{cam_id}_snap.jpg')

    logger.debug('Taking snapshots...')
    img1 = cam.snap()
    img2 = cam.snap()

    logger.debug('Comparing snapshots')
    img_arr, ctrs = detect_motion_with_diff(
        img_arr=np.asarray(img2, dtype=np.uint8),
        prev_img_arr=np.asarray(img1, dtype=np.uint8)
    )
    img = Image.fromarray(img_arr)

    img.save(snap_img_path, quality=quality, optimize=is_optimize)

    logger.debug('Uploading to slack...')
    upload_to_slack(
        snap_img_path,
        slack_client=get_slack_client(),
        channel=cam.slack_channel,
        text=build_motion_message(detection_type, cam, detection_time, cnts=len(ctrs))
    )


@celery_app.task
def take_gif(cam_id: id, detection_type: str, detection_time: str, take_seconds: int = 5, quality: int = 35):
    cam = get_cam(cam_id)

    gif_path = BASE_PATH.joinpath(f'cam_{cam_id}_motion.gif')

    n_frames = take_seconds * 4  # 4 fps
    logger.info(f'Generating gif of {take_seconds}s ({n_frames} frames)')

    cap = cam.stream()
    completed_frames = []  # type: List[Image.Image]
    cnts_per_frame = []
    prev_rgb_frame_arr = None

    logger.debug('Beginning frame collection')
    for i in range(n_frames):
        _, frame = cap.read()
        if frame.shape[1] > 640:
            frame = imutils.resize(frame, width=640)
        rgb_frame_arr = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        rgb_frame_arr_drawn, cnts = detect_motion_with_diff(img_arr=rgb_frame_arr, prev_img_arr=prev_rgb_frame_arr)
        # TODO: Capture cnts per frame and put average in slack msg
        cnts_per_frame.append(len(cnts))
        completed_frames.append(Image.fromarray(rgb_frame_arr_drawn))
        prev_rgb_frame_arr = rgb_frame_arr.copy()

    cap.release()
    logger.debug('Completed frame collection')

    logger.debug('Saving gif...')
    # PIL method
    completed_frames[0].save(
        gif_path,
        save_all=True,
        append_images=completed_frames[1:],
        optimize=True,
        quality=quality,
        duration=200,
        loop=0
    )

    avg_cnts_per_frame = sum(cnts_per_frame) / len(cnts_per_frame)
    if avg_cnts_per_frame < 0.1:
        logger.debug(f'Average contours per frame ({avg_cnts_per_frame}) was below threshold (0.1). Skipping upload.')
    else:
        logger.debug('Uploading gif to Slack...')
        upload_to_slack(
            gif_path,
            slack_client=get_slack_client(),
            channel=os.getenv('GIF_CHANNEL', cam.slack_channel),
            text=build_motion_message(detection_type, cam, detection_time, avg_cnts_per_frame=avg_cnts_per_frame)
        )
