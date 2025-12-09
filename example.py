import logging
import multiprocessing
import signal
import sys
import time

import cv2
import keyboard

from config import AppConfig, CaptureRegion, OBSConfig, adjust_region_to_multiple
from grabbers import get_grabber
from utils.fps import FPSCounter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

WINDOW_TITLE = "some_window"
ACTIVATION_HOTKEY = 58
SHOW_PREVIEW = True
GRABBER_TYPE = "mss"  # or "obs_vc" if you wanna use OBS Virtual Camera for a better performance (in some cases)

# separate settings for OBS Virtual Camera grabber
OBS_DEVICE_INDEX = -1
OBS_DEVICE_NAME = "OBS Virtual Camera"


def create_config() -> AppConfig:
    try:
        from utils.win32 import get_window_rect
        rect = get_window_rect(WINDOW_TITLE)
        region = CaptureRegion(
            left=rect[0],
            top=rect[1],
            width=rect[2],
            height=rect[3],
        )
    except Exception:
        region = CaptureRegion()

    region = adjust_region_to_multiple(region, 32)

    config = AppConfig(
        window_title=WINDOW_TITLE,
        activation_hotkey=ACTIVATION_HOTKEY,
        show_preview=SHOW_PREVIEW,
        grabber_type=GRABBER_TYPE,
        capture_region=region,
    )

    if GRABBER_TYPE == "obs_vc":
        config.obs = OBSConfig(
            device_index=OBS_DEVICE_INDEX,
            device_name=OBS_DEVICE_NAME,
        )
        config.grabber_options = {
            "device_index": OBS_DEVICE_INDEX,
            "device_name": OBS_DEVICE_NAME,
        }

    return config


def grab_process(
    queue: multiprocessing.JoinableQueue,
    stop_event: multiprocessing.Event,
    config: AppConfig,
) -> None:
    try:
        grabber = get_grabber(config.grabber_type, **config.grabber_options)
    except Exception as e:
        logger.error(f"Failed to initialize grabber: {e}")
        stop_event.set()
        return

    grab_area = config.capture_region.to_dict()

    while not stop_event.is_set():
        try:
            img = grabber.get_image(grab_area)
            if img is None:
                continue

            while not queue.empty():
                try:
                    queue.get_nowait()
                except BaseException:
                    break

            queue.put_nowait(img)
            queue.join()

        except Exception as e:
            logger.error(f"Capture error: {e}")
            stop_event.set()
            break

    grabber.cleanup()
    logger.info("Capture process stopped")


def process_frame(
    queue: multiprocessing.JoinableQueue,
    stop_event: multiprocessing.Event,
    activated: multiprocessing.Event,
    config: AppConfig,
) -> None:
    fps = FPSCounter()
    font = cv2.FONT_HERSHEY_SIMPLEX

    while not stop_event.is_set():
        if queue.empty():
            time.sleep(0.001)
            continue

        try:
            img = queue.get_nowait()
            queue.task_done()
        except BaseException:
            continue

        if activated.is_set():
            pass

        if config.show_preview:
            current_fps = fps()
            cv2.putText(
                img,
                f"{current_fps:.1f}",
                (20, 120),
                font,
                1.7,
                (0, 255, 0),
                7,
                cv2.LINE_AA,
            )
            cv2.imshow("Preview", cv2.resize(img, config.preview_size))

            if cv2.waitKey(1) & 0xFF == ord("q"):
                stop_event.set()

    cv2.destroyAllWindows()
    logger.info("Processing stopped")


def main() -> int:
    config = create_config()

    stop_event = multiprocessing.Event()
    activated = multiprocessing.Event()
    queue = multiprocessing.JoinableQueue()

    def toggle_activation():
        if activated.is_set():
            activated.clear()
            logger.info("Deactivated")
        else:
            activated.set()
            logger.info("Activated")

    keyboard.add_hotkey(config.activation_hotkey, toggle_activation)

    def shutdown(signum, frame):
        logger.info("Shutting down...")
        stop_event.set()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    processes = [
        multiprocessing.Process(
            target=grab_process,
            args=(queue, stop_event, config),
        ),
        multiprocessing.Process(
            target=process_frame,
            args=(queue, stop_event, activated, config),
        ),
    ]

    for p in processes:
        p.start()

    try:
        while not stop_event.is_set():
            time.sleep(0.1)
    except KeyboardInterrupt:
        stop_event.set()

    for p in processes:
        p.join(timeout=3)
        if p.is_alive():
            p.terminate()

    logger.info("Shutdown complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
