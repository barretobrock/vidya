from enum import StrEnum
from typing import (
    List,
    Optional,
    Tuple,
)

from PIL import Image
import cv2
from loguru import logger
import numpy as np
from numpy.typing import NDArray


class MotionDetectionType(StrEnum):
    DIFF = 'DIFF'       # Determine motion by comparing difference in previous frame
    BGSUB = 'BGSUB'     # Determine motion by using background subtraction


class GIFHandleMethod(StrEnum):
    NORMAL = 'NORMAL'           # Normal: Preserve frames (large files)
    OPTIMIZED = 'OPTIMIZED'     # Optimized: Use alpha channel to eliminate unchanged parts of frames (small files)


class MotionDetector:
    DEFAULT_THRESH = 20                 # For motion detection. Was 20
    DEFAULT_KERNEL_SIZE = (5, 5)        # For blurring
    DEFAULT_MIN_CONTOUR_AREA = 200
    DEFAULT_MAX_CONTOUR_AREA = 90_000
    GREEN = (0, 255, 0)
    GREEN_TRANSP = (0, 255, 0, 255)
    RED = (255, 0, 0)
    RED_TRANSP = (255, 0, 0, 255)
    GRAY = cv2.COLOR_BGR2GRAY

    def __init__(
            self,
            detection_type: MotionDetectionType = MotionDetectionType.DIFF,
            is_gif: bool = False,
            gif_handle_method: GIFHandleMethod = GIFHandleMethod.NORMAL
    ):
        self.detection_type = detection_type
        self.is_gif = is_gif
        self.gif_handle_method = gif_handle_method

        if self.gif_handle_method == GIFHandleMethod.NORMAL:
            self.color_style = cv2.COLOR_BGR2RGB
        else:
            self.color_style = cv2.COLOR_BGR2RGBA

    def batch_process_motion_detect_with_diff(
            self,
            frames: List[NDArray]
    ) -> Tuple[List[NDArray], float]:
        """Process the original frames into ones with motion on them depending on the parameters set"""
        prev_img_blur_arr = None
        prev_img_mask = None
        processed_frames = []
        cntrs_per_frame = []

        for i, frame in enumerate(frames):
            logger.debug(f'Working on frame {i + 1}...')
            # Convert frame from camera's color to RGB or RGBA, depending on GIF handling style
            rgb_frame_arr = cv2.cvtColor(frame, self.color_style)

            # Detect motion
            fg_mask, prev_img_blur_arr = self.motion_detect_with_diff(
                img_arr=rgb_frame_arr,
                prev_img_blur_arr=prev_img_blur_arr
            )
            # Apply contouring
            contours = self.extract_contours(fg_mask=fg_mask)
            if self.gif_handle_method == GIFHandleMethod.NORMAL:
                rgb_frame_arr = self.contouring_normal(img_arr=rgb_frame_arr, contours=contours)
            else:
                rgb_frame_arr, prev_img_mask = self.contouring_optimized(
                    i=i,
                    img_arr=rgb_frame_arr,
                    fg_mask=fg_mask,
                    past_mask=prev_img_mask,
                    contours=contours
                )
            processed_frames.append(rgb_frame_arr)
            cntrs_per_frame.append(len(contours))

        try:
            avg_cnts_per_frame = sum(cntrs_per_frame) / len(cntrs_per_frame)
        except ZeroDivisionError:
            avg_cnts_per_frame = 0

        return processed_frames, avg_cnts_per_frame

    @staticmethod
    def motion_detect_with_bgsub(
            img_arr: NDArray,
            bg_sub: cv2.BackgroundSubtractorMOG2
    ) -> Tuple[NDArray, cv2.BackgroundSubtractorMOG2]:
        if bg_sub is None:
            logger.debug('Starting up new background subtractor...')
            bg_sub = cv2.createBackgroundSubtractorMOG2()
        fg_mask = bg_sub.apply(img_arr)

        return fg_mask, bg_sub

    @classmethod
    def grey_and_blur_img(cls, img_arr: NDArray) -> NDArray:
        """Greyscales and blurs an image"""
        # Set to grayscale
        img_gray_arr = cv2.cvtColor(img_arr, cls.GRAY)
        # Blur slightly
        img_blur_arr = cv2.GaussianBlur(src=img_gray_arr, ksize=cls.DEFAULT_KERNEL_SIZE, sigmaX=0)
        return img_blur_arr

    def motion_detect_with_diff(
            self,
            img_arr: NDArray,
            prev_img_blur_arr: NDArray = None
    ) -> Tuple[NDArray, NDArray]:
        img_blur_arr = self.grey_and_blur_img(img_arr=img_arr)

        if prev_img_blur_arr is None:
            prev_img_blur_arr = img_blur_arr

        diff_frame = cv2.absdiff(src1=img_blur_arr, src2=prev_img_blur_arr)
        # Dilute img to make differences more visible
        kernel = np.ones(self.DEFAULT_KERNEL_SIZE)
        diff_frame = cv2.dilate(diff_frame, kernel, 1)

        fg_mask = cv2.threshold(src=diff_frame, thresh=self.DEFAULT_THRESH, maxval=255, type=cv2.THRESH_BINARY)[1]
        # Return the foreground masked frame and the greyed/blurred current frame
        #   to serve as the previous frame next iteration.
        return fg_mask, img_blur_arr

    def extract_contours(self, fg_mask: NDArray) -> List[NDArray]:
        contours, hierarchy = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        # Filter contours by area thresholds
        target_cntrs = []
        for cnt in contours:
            contour_area = cv2.contourArea(cnt)
            if self.DEFAULT_MAX_CONTOUR_AREA > contour_area > self.DEFAULT_MIN_CONTOUR_AREA:
                target_cntrs.append(cnt)
        if n_cntrs := len(target_cntrs) > 0:
            logger.debug(f'{n_cntrs} to be applied to frame.')
        return target_cntrs

    @staticmethod
    def contouring_normal(img_arr: NDArray, contours: List[NDArray]) -> NDArray:
        """The 'normal' contouring method - just drawing on the frame"""
        for i, cnt in enumerate(contours):
            # logger.debug(f'Contour ({i + 1}) area: {cv2.contourArea(cnt)}')
            x, y, w, h = cv2.boundingRect(cnt)
            thickness = 1
            color = (255, 0, 0)
            img_arr = cv2.drawContours(img_arr.copy(), cnt, -1, (0, 255, 0), 1)
            img_arr = cv2.rectangle(img_arr, (x, y), (x + w, y + h), color, thickness)

            # cntrs_out.append(((x, y), (x + w, y + h)))
        return img_arr

    @staticmethod
    def contouring_optimized(
            i: int,
            img_arr: NDArray,
            fg_mask: NDArray,
            past_mask: Optional[NDArray],
            contours: List[NDArray]
    ) -> Tuple[NDArray, Optional[NDArray]]:
        """The 'optimized' contouring method - drawing on semi-transparent frames

        Since we have semi-transparent frames, we have to clean up previous frames' drawings
        before we can draw on the new frame.
        """
        img_orig = Image.fromarray(img_arr.copy(), 'RGBA')
        img_orig_past_mask = None

        if past_mask is not None:
            past_img_mask_img = Image.fromarray(past_mask)
            past_img_mask_img = past_img_mask_img.resize(img_orig.size)
            # Make a copy of the original img to apply the mask
            img_orig_past_mask = img_orig.copy()
            # Apply the mask
            img_orig_past_mask.putalpha(past_img_mask_img)

        if i == 0:
            # Don't do anything to the background
            img_out = img_orig.copy()
        elif fg_mask.min() == 0 and fg_mask.max() == 0:
            # If no foreground activity, blank out the image.
            img_out = Image.new('RGBA', img_orig.size, (255, 255, 255, 0))
        else:
            img_out = img_orig.copy()
            # Apply activity mask to image
            fg_mask_img = Image.fromarray(fg_mask)
            fg_mask_img = fg_mask_img.resize(img_orig.size)
            img_out.putalpha(fg_mask_img)

        img_arr_out = np.asarray(img_out, dtype=np.uint8)

        if img_orig_past_mask is not None:
            # If we have a past mask, merge it in to the main image now. Make sure it goes on bottom.
            img_out = Image.fromarray(img_arr_out, mode='RGBA')
            img_out.paste(img_orig_past_mask, (0, 0), img_orig_past_mask)
            # Convert back to array
            img_arr_out = np.asarray(img_out, dtype=np.uint8)

        img_cnt_mask = None

        if len(contours) > 0:
            # Make a layer for contours
            img_cnt = Image.new('RGBA', img_orig.size, (255, 255, 255, 0))
            img_cnt_arr = np.asarray(img_cnt, dtype=np.uint8)

            for i, cnt in enumerate(contours):
                logger.debug(f'Contour ({i + 1}) area: {cv2.contourArea(cnt)}')
                x, y, w, h = cv2.boundingRect(cnt)
                thickness = 1
                green_trans = (0, 255, 0, 255)
                red_trans = (255, 0, 0, 255)
                # Apply contours and the bounding rectangle to the image layer
                img_cnt_arr = cv2.drawContours(img_cnt_arr.copy(), cnt, -1, green_trans, thickness)
                img_cnt_arr = cv2.rectangle(img_cnt_arr, (x, y), (x + w, y + h), red_trans, thickness)

            # Take the image layer, merge the contours layer on top of it
            img_out = Image.fromarray(img_arr_out, mode='RGBA')
            img_cnt = Image.fromarray(img_cnt_arr, mode='RGBA')
            img_out.paste(img_cnt, (0, 0), img_cnt)
            # Convert back to array
            img_arr_out = np.asarray(img_out, dtype=np.uint8)
            # Make a mask of the contour layer to pass in to the next iteration
            img_cnt_mask = cv2.inRange(img_cnt_arr, lowerb=np.array([0, 0, 0, 255]),
                                       upperb=np.array([255, 255, 255, 255]))

        return img_arr_out, img_cnt_mask
