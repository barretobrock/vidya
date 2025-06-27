import os
import random
import string
from typing import (
    List,
    Optional,
    Tuple,
)

from PIL import Image
import cv2
import imutils
from loguru import logger
import numpy as np
import requests

from vidya import ROOT
from vidya.core.motion_detect import detect_motion_with_diff


class IPCamera:
    DEFAULT_WIDTH = 640

    def __init__(self, cam_id: int):
        self.ip_subnet = os.environ['IP_SUBNET']
        self.cam_id = cam_id
        self._usr = os.environ[f'CAM_{cam_id}_USR']
        self._pwd = os.environ[f'CAM_{cam_id}_PWD']
        self.cam_name = os.environ[f'CAM_{cam_id}_NAME']
        self.cam_ip = f'192.168.{self.ip_subnet}.{self.cam_id}'
        self.channel = int(os.environ[f'CAM_{cam_id}_CHANNEL'])
        self.stream_name = os.environ[f'CAM_{cam_id}_STREAM']
        self.slack_channel = os.environ[f'CAM_{cam_id}_SLACK']
        self._base_url = f'http://{self.cam_ip}/cgi-bin/api.cgi?'

        self.token = None
        self.token_file = ROOT.joinpath(f'.sessions/{self.cam_id}_{self.cam_name}')
        if self.token_file.exists():
            logger.info(f'Reading in existing token for camera {self.cam_name}.')
            self.token = self.token_file.read_text()
        else:
            self.login()

        self.rs = ''.join(random.choice(string.ascii_letters) for _ in range(24))

    def login(self):
        logger.info(f'Generating new token for camera {self.cam_name}.')
        resp = requests.post(f'{self._base_url}cmd=Login', json=[{
            'cmd': 'Login',
            'param': {
                'User': {
                    'Version': '0',
                    'userName': self._usr,
                    'password': self._pwd
                }
            }
        }])
        self.token = resp.json()[0]['value']['Token']['name']
        self.token_file.write_text(self.token)

    def _snap_req(self) -> np.typing.NDArray:
        # logger.debug('Taking snap...')
        resp = requests.get(f'{self._base_url}cmd=Snap&channel=0&rs={self.rs}&token={self.token}')
        img_arr = cv2.imdecode(np.asanyarray(bytearray(resp.content), dtype=np.uint8), -1)
        # logger.debug('Completed snap...')
        if img_arr is None:
            resp_dict = resp.json()[0]
            if err_dict := resp_dict.get('error'):
                err_text = 'Unexpected error: {detail}: {rspCode}'.format(**err_dict)
            else:
                err_text = 'Unknown?'
            if err_dict['rspCode'] == -6:
                # Need to login again (expired token?)
                logger.warning('Potential expired token - attempting to renew.')
                self.login()
                return self._snap_req()
            else:
                raise ValueError(err_text)
        return img_arr

    def snap(self, n_snaps: int = 1, target_width: Optional[int] = DEFAULT_WIDTH) -> List[Image.Image]:
        raw_img_arrs = []  # type: List[np.typing.NDArray]
        for i in range(n_snaps):
            raw_img_arrs.append(self._snap_req())

        imgs = []
        for img_arr in raw_img_arrs:
            # Color correction
            img_arr = cv2.cvtColor(img_arr, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(img_arr)
            if target_width is not None:
                ratio = img.width / target_width
                img = img.resize((int(img.width / ratio), int(img.height / ratio)))
            imgs.append(img)
        return imgs

    def snap_with_motion(self, target_width: Optional[int] = DEFAULT_WIDTH) -> Tuple[Image.Image, int]:
        logger.debug('Taking snapshots...')
        imgs = self.snap(n_snaps=2, target_width=target_width)

        logger.debug('Comparing snapshots')
        img_arr, ctrs = detect_motion_with_diff(
            img_arr=np.asarray(imgs[1], dtype=np.uint8),
            prev_img_arr=np.asarray(imgs[0], dtype=np.uint8)
        )
        img = Image.fromarray(img_arr)
        return img, len(ctrs)

    def stream(self) -> cv2.VideoCapture:
        rtsp_url = f'rtsp://{self._usr}:{self._pwd}@{self.cam_ip}:554/{self.stream_name}'
        return cv2.VideoCapture(rtsp_url)

    def stream_gif_with_motion(self, n_frames: int, target_width: Optional[int] = DEFAULT_WIDTH) -> Tuple[List[Image.Image], float]:
        cap = self.stream()
        if not cap.isOpened():
            # Failed to open for some reason
            ValueError('Stream was unable to be opened.')

        completed_frames = []  # type: List[Image.Image]
        cnts_per_frame = []
        prev_rgb_frame_arr = None

        logger.debug('Beginning frame collection')
        for i in range(n_frames):
            _, frame = cap.read()
            if frame.shape[1] > target_width:
                frame = imutils.resize(frame, width=target_width)
            rgb_frame_arr = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            rgb_frame_arr_drawn, cnts = detect_motion_with_diff(img_arr=rgb_frame_arr, prev_img_arr=prev_rgb_frame_arr)
            cnts_per_frame.append(len(cnts))
            completed_frames.append(Image.fromarray(rgb_frame_arr_drawn))
            prev_rgb_frame_arr = rgb_frame_arr.copy()

        cap.release()
        logger.debug('Completed frame collection')

        try:
            avg_cnts_per_frame = sum(cnts_per_frame) / len(cnts_per_frame)
        except ZeroDivisionError:
            avg_cnts_per_frame = 0

        return completed_frames, avg_cnts_per_frame
