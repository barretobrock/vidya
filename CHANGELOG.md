# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

_Note: 'Unreleased' section below is used for untagged changes that will be issued with the next version bump_

### [Unreleased] - 2024-00-00
#### Added
#### Changed
#### Deprecated
#### Removed
#### Fixed
#### Security
__BEGIN-CHANGELOG__
 
### [0.1.7] - 2025-06-30
#### Added
 - Improved GIF handling to significantly reduce file size by leveraging alpha channels 
#### Changed
 - Motion detection now a class to couple some methods
 
### [0.1.6] - 2025-06-26
#### Added
 - Avoid `ZeroDivisionError` when calculating avg contours in gif
 - Token generation method is way less greedy now
#### Changed
 - Speed up snap process by delaying full process in favor of taking a comparison snap sooner
#### Removed
 - FFMPEG capture mode from RTSP steam (seems faster?)
 
### [0.1.5] - 2025-06-19
#### Added
 - task broker instances for async request handling: celery, redis  
#### Changed
 - request params now include `quality`
 - gif maker now builds via `PIL.Image` instead of `imageio`
 
### [0.1.4] - 2025-06-18
#### Added
 - motion detection via image difference
#### Changed
 - motion detection methods share contour application method
#### Removed
 - gif optimization step
 
### [0.1.3] - 2025-06-18
#### Added
 - `opencv-python` dep was missing
#### Changed
 - `run.py` to `wsgi.py`
 
### [0.1.2] - 2025-06-18
#### Added
 - Separated functionality of base snapshots and regular (comparison) snapshots.
 
### [0.1.1] - 2025-06-18
#### Added
 - Production install improvements to the Makefile
 - frozen reqs to avoid poetry dep in prod

### [0.1.0] - 2025-05-26
#### Added
 - Initiated project

__END-CHANGELOG__