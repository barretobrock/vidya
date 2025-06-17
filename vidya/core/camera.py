import os
import random
import string
from typing import Optional

import cv2
import numpy as np
from PIL import Image
import requests


class IPCamera:

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
        self.token = None
        # cam = Camera(self.cam_ip, username=self._usr, password=self._pwd)
        # self.token = cam.token
        self._base_url = f'http://{self.cam_ip}/cgi-bin/api.cgi?'
        self.login()
        self.rs = ''.join(random.choice(string.ascii_letters) for _ in range(24))

    def login(self):
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

    def snap(self, target_width: Optional[int] = 640) -> Image.Image:
        resp = requests.get(f'{self._base_url}cmd=Snap&channel=0&rs={self.rs}&token={self.token}')
        img_arr = cv2.imdecode(np.asanyarray(bytearray(resp.content), dtype=np.uint8), -1)
        if img_arr is None:
            resp_dict = resp.json()[0]
            if err_dict := resp_dict.get('error'):
                err_text = 'Unexpected error: {detail}: {rspCode}'.format(**err_dict)
            else:
                err_text = 'Unknown?'
            if err_dict['rspCode'] == -6:
                # Need to login again (expired token?)
                self.login()
                img = self.snap()
                return img
            else:
                raise ValueError(err_text)
        # Color correction
        img_arr = cv2.cvtColor(img_arr, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(img_arr)
        if target_width is not None:
            ratio = img.width / 640
            img = img.resize((int(img.width / ratio), int(img.height / ratio)))
        return img


    def stream(self):
        rtsp_url = f'rtsp://{self._usr}:{self._pwd}@{self.cam_ip}:554/{self.stream_name}'
        return cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
