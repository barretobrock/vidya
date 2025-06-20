from typing import (
    List,
    Tuple,
)

import cv2
from loguru import logger
import numpy as np
from numpy.typing import NDArray

DEFAULT_THRESH = 20
DEFAULT_KERNEL_SIZE = (5, 5)


def detect_motion_with_diff(img_arr: NDArray, prev_img_arr: NDArray = None) -> Tuple[NDArray, List[Tuple]]:
    img_arr_gray = cv2.cvtColor(img_arr, cv2.COLOR_BGR2GRAY)
    img_arr_blur = cv2.GaussianBlur(src=img_arr_gray, ksize=DEFAULT_KERNEL_SIZE, sigmaX=0)

    if prev_img_arr is None:
        prev_img_arr_blur = img_arr_blur
    else:
        prev_img_arr = cv2.cvtColor(prev_img_arr, cv2.COLOR_BGR2GRAY)
        prev_img_arr_blur = cv2.GaussianBlur(src=prev_img_arr, ksize=DEFAULT_KERNEL_SIZE, sigmaX=0)

    diff_frame = cv2.absdiff(src1=img_arr_blur, src2=prev_img_arr_blur)
    # Dilute img to make differences more visible
    kernel = np.ones((5, 5))
    diff_frame = cv2.dilate(diff_frame, kernel, 1)

    thresh_frame = cv2.threshold(src=diff_frame, thresh=DEFAULT_THRESH, maxval=255, type=cv2.THRESH_BINARY)[1]
    return apply_contours(img_arr=img_arr, fg_mask=thresh_frame)


def detect_motion_with_bgsub(
        img_arr: NDArray,
        bg_sub: cv2.BackgroundSubtractorMOG2 = None
) -> Tuple[NDArray, cv2.BackgroundSubtractorMOG2, List[Tuple]]:

    if bg_sub is None:
        logger.debug('Starting up new background subtractor...')
        bg_sub = cv2.createBackgroundSubtractorMOG2()
    # Create foreground mask by removing background
    fg_mask = bg_sub.apply(img_arr)
    img_arr, cnts = apply_contours(img_arr=img_arr, fg_mask=fg_mask)
    return img_arr, bg_sub, cnts


def apply_contours(img_arr: NDArray, fg_mask: NDArray) -> Tuple[NDArray, List[Tuple]]:
    logger.debug('Generating contours...')
    contours, hierarchy = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    logger.debug(f'Total initial contours: {len(contours)}')

    logger.debug(f'Removing contours (up to {len(contours)}) by area...')
    min_contour_area = 200
    max_contour_area = 90_000
    large_contours = [cnt for cnt in contours if max_contour_area > cv2.contourArea(cnt) > min_contour_area]

    logger.debug(f'Applying {len(large_contours)} contours to image...')
    img_arr_out = img_arr.copy()
    cnts_out = []
    for i, cnt in enumerate(large_contours):
        logger.debug(f'Contour ({i + 1}) area: {cv2.contourArea(cnt)}')
        x, y, w, h = cv2.boundingRect(cnt)
        thickness = 1
        color = (255, 0, 0)
        img_arr_out = cv2.drawContours(img_arr_out, cnt, -1, (0, 255, 0), 1)
        img_arr_out = cv2.rectangle(img_arr_out, (x, y), (x + w, y + h), color, thickness)

        cnts_out.append(((x, y), (x + w, y + h)))

    return img_arr_out, cnts_out
