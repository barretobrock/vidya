import time
from typing import (
    List,
    Tuple,
    Union
)

import cv2
import imutils
from loguru import logger
import numpy as np
from numpy.typing import NDArray
from PIL import Image


DEFAULT_THRESH = 180

def detect_motion(
        img: Union[Image.Image, NDArray],
        bg_sub: cv2.BackgroundSubtractorMOG2 = None
) -> Tuple[Union[Image.Image, NDArray], cv2.BackgroundSubtractorMOG2, List[Tuple]]:
    if isinstance(img, Image.Image):
        ret_as_arr = False
        img_arr = np.asarray(img, dtype=np.uint8)
    else:
        ret_as_arr = True
        img_arr = img

    if bg_sub is None:
        logger.debug('Starting up new background subtractor...')
        bg_sub = cv2.createBackgroundSubtractorMOG2()
    # Create foreground mask by removing background
    fg_mask = bg_sub.apply(img_arr)

    logger.debug('Generating contours...')
    contours, hierarchy = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    logger.debug(f'Total initial contours: {len(contours)}')

    logger.debug(f'Removing contours (up to {len(contours)}) by area...')
    min_contour_area = 250
    max_contour_area = 90_000
    large_contours = [cnt for cnt in contours if max_contour_area > cv2.contourArea(cnt) > min_contour_area]

    logger.debug(f'Applying {len(large_contours)} contours to image...')
    img_out = img_arr.copy()
    cnts_out = []
    for i, cnt in enumerate(large_contours):
        logger.debug(f'Contour ({i + 1}) area: {cv2.contourArea(cnt)}')
        x, y, w, h = cv2.boundingRect(cnt)
        thickness = 2
        color = (255, 0, 0)
        img_out = cv2.drawContours(img_out, cnt, -1, (0, 255, 0), 1)
        img_out = cv2.rectangle(img_out, (x, y), (x + w, y + h), color, thickness)

        cnts_out.append(((x, y), (x + w, y + h)))

    if not ret_as_arr:
        return Image.fromarray(img_out), bg_sub, cnts_out
    return img_out, bg_sub, cnts_out


