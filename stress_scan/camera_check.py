"""
Camera diagnostic - run this on a computer where the camera is flaky and send the output back.

    Windows:  .venv\\Scripts\\python.exe -m stress_scan.camera_check
    macOS:    .venv/bin/python -m stress_scan.camera_check

Run it from the StudyPet folder (the one that contains start_windows.bat).
It tries every camera backend/index combination the app tries, prints what happened for each,
then reads ~3 seconds of frames from the one that worked and reports speed and brightness.
"""

import os
import sys
import time


def main():
    from stress_scan import live_scan

    print("=== StudyPet camera check ===")
    print("Python :", sys.version.split()[0], "| platform:", sys.platform)
    try:
        import cv2
        print("OpenCV :", cv2.__version__, "|", os.path.dirname(cv2.__file__))
    except Exception as e:
        print("OpenCV could not be imported:", type(e).__name__, e)
        return 1
    print()

    try:
        cap = live_scan.open_webcam(log=print)
    except live_scan.CameraUnavailableError as e:
        print()
        print("RESULT: no working camera found.")
        print(e)
        return 2

    print()
    print("Reading frames for about 3 seconds...")
    count = 0
    failed = 0
    brightness = []
    start = time.time()
    while time.time() - start < 3.0:
        ok, frame = cap.read()
        if not ok or frame is None:
            failed += 1
            time.sleep(0.03)
            continue
        count += 1
        brightness.append(float(frame.mean()))
    height, width = (frame.shape[:2] if count else (0, 0))
    cap.release()

    elapsed = max(time.time() - start, 0.001)
    print(f"Frames read : {count}  (failed reads: {failed})")
    print(f"Speed       : {count / elapsed:.1f} frames per second")
    if brightness:
        print(f"Brightness  : average {sum(brightness) / len(brightness):.1f} out of 255")
    print(f"Frame size  : {width} x {height}")
    print()
    print("RESULT: OK" if count >= 10 else "RESULT: the camera opened but delivers too few frames.")
    return 0 if count >= 10 else 3


if __name__ == "__main__":
    sys.exit(main())
