from enum import StrEnum
import os
from typing import List  # noqa: F401

from celery import Celery  # noqa: F401
from celery.result import AsyncResult  # noqa: F401
from celery.worker.request import Request  # noqa: F401
from loguru import logger

from vidya import ROOT
from vidya.app import create_app
from vidya.core.notify import upload_to_slack
from vidya.routes.helpers import (
    build_motion_message,
    get_cam,
    get_slack_client,
)

BASE_PATH = ROOT.joinpath('snaps')
app = create_app()
celery_app = app.extensions['celery']  # type: Celery


class CaptureMode(StrEnum):
    SNAP_ONLY = 'SNAP_ONLY'
    GIF_ONLY = 'GIF_ONLY'
    SNAP_AND_GIF = 'SNAP_AND_GIF'


@celery_app.task
def take_snapshot(cam_id: id, detection_type: str, detection_time: str, quality: int = 35,
                  is_optimize: bool = True):
    cam = get_cam(cam_id)
    logger.debug(f'Handling SNAP for camera: {cam.cam_name}')

    snap_img_path = BASE_PATH.joinpath(f'cam_{cam_id}_snap.jpg')

    img, n_ctrs = cam.snap_with_motion()

    img.save(snap_img_path, quality=quality, optimize=is_optimize)

    logger.debug('Uploading to slack...')
    upload_to_slack(
        snap_img_path,
        slack_client=get_slack_client(),
        channel=cam.slack_channel,
        text=build_motion_message(detection_type, cam, detection_time, cnts=n_ctrs)
    )


@celery_app.task
def take_gif(cam_id: id, detection_type: str, detection_time: str, take_seconds: int = 5, quality: int = 35,
             fps: int = 10):
    cam = get_cam(cam_id)
    logger.debug(f'Handling GIF for camera: {cam.cam_name}')

    gif_path = BASE_PATH.joinpath(f'cam_{cam_id}_motion.gif')

    n_frames = take_seconds * fps
    logger.info(f'Generating gif of {take_seconds}s ({n_frames} frames)')
    completed_frames, avg_cnts_per_frame = cam.stream_gif_with_motion(n_frames)

    logger.debug('Saving gif...')
    # PIL method
    completed_frames[0].save(
        gif_path,
        save_all=True,
        append_images=completed_frames[1:],
        optimize=True,
        quality=quality,
        duration=100,
        loop=0
    )

    if avg_cnts_per_frame < 0.1:
        logger.info(f'Average contours per frame ({avg_cnts_per_frame}) was below threshold (0.1). Skipping upload.')
    else:
        logger.info('Uploading gif to Slack...')
        upload_to_slack(
            gif_path,
            slack_client=get_slack_client(),
            channel=os.getenv('GIF_CHANNEL', cam.slack_channel),
            text=build_motion_message(detection_type, cam, detection_time, avg_cnts_per_frame=avg_cnts_per_frame)
        )
