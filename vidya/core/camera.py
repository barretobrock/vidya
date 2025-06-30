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
from vidya.core.motion_detect import (
    GIFHandleMethod,
    MotionDetectionType,
    MotionDetector,
)


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
        # TODO: Everything below here should be wrapped into a convenience method in motion detector
        img_arr1, img_arr2 = [np.asarray(x, dtype=np.uint8) for x in imgs]

        logger.debug('Comparing snapshots')
        md = MotionDetector(detection_type=MotionDetectionType.DIFF)
        mask, blur_arr = md.motion_detect_with_diff(
            img_arr=img_arr2,
            prev_img_blur_arr=md.grey_and_blur_img(img_arr1)
        )
        cntrs = md.extract_contours(fg_mask=mask)
        img_arr = md.contouring_normal(img_arr2, contours=cntrs)

        img = Image.fromarray(img_arr)
        return img, len(cntrs)

    def stream(self) -> cv2.VideoCapture:
        rtsp_url = f'rtsp://{self._usr}:{self._pwd}@{self.cam_ip}:554/{self.stream_name}'
        return cv2.VideoCapture(rtsp_url)

    def stream_gif_with_motion(self, n_frames: int, target_width: Optional[int] = DEFAULT_WIDTH, method: str = 'normal') -> Tuple[List[Image.Image], float]:
        cap = self.stream()
        if not cap.isOpened():
            # Failed to open for some reason
            ValueError('Stream was unable to be opened.')

        org_frames = []

        logger.debug('Beginning frame collection')
        for i in range(n_frames):
            _, frame = cap.read()
            if frame.shape[1] > target_width:
                frame = imutils.resize(frame, width=target_width)
            org_frames.append(frame)
        cap.release()
        logger.debug('Completed frame collection')

        logger.debug('Correcting frames & processing for motion.')

        md = MotionDetector(detection_type=MotionDetectionType.DIFF, gif_handle_method=GIFHandleMethod.OPTIMIZED)
        processed_frames, avg_cntrs_per_frame = md.batch_process_motion_detect_with_diff(frames=org_frames)

        completed_frames = [Image.fromarray(x) for x in processed_frames]

        return completed_frames, avg_cntrs_per_frame
