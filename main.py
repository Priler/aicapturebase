import logging, os

# Import required grabber from available under utils/grabbers
from utils.grabbers.obs_vc import Grabber
from pygrabber.dshow_graph import FilterGraph

# Import FPS measurement utility
from utils.fps import FPS

# Import mouse controls, keyboard controls and some helpers
from utils.controls.mouse.win32 import MouseControls
from utils.win32 import WinHelper
from utils.cv2 import resize_image_to_fit_multiply_of_32
import keyboard

# Import custom (more precise) sleep implementation
from utils.time import sleep

# default stuff
import cv2
import multiprocessing


# CONFIG
GAME_WINDOW_TITLE = "some_window"  # aimlab_tb, FallGuys_client, Counter-Strike: Global Offensive - Direct3D 9, etc
ACTIVATION_HOTKEY = 58  # 58 = CAPS-LOCK
_show_cv2 = True

obs_vc_device_index = -1 # -1 to find by the given name
obs_vc_device_name = "OBS Virtual Camera"

# used by the script
# game_window_rect = WinHelper.GetWindowRect(GAME_WINDOW_TITLE, (8, 30, 16, 39)) # cut the borders
game_window_rect = WinHelper.GetWindowRect(GAME_WINDOW_TITLE, (0, 0, 0, 0)) # cut the borders
game_window_rect = resize_image_to_fit_multiply_of_32(list(game_window_rect))
_activated = False


def grab_process(q):
    grabber = Grabber()

    if grabber.type == "obs_vc":
        if obs_vc_device_index != -1:
            # init device by given index
            grabber.obs_vc_init(obs_vc_device_index)
        else:
            # init device by given name
            graph = FilterGraph()

            print(graph.get_input_devices())

            try:
                device = grabber.obs_vc_init(graph.get_input_devices().index(obs_vc_device_name))
            except ValueError as e:
                logging.error(f'Could not find OBS VC device with name "{obs_vc_device_name}"')
                logging.error(e)
                os._exit(1)

    while True:
        try:
            img = grabber.get_image({"left": int(game_window_rect[0]), "top": int(game_window_rect[1]), "width": int(game_window_rect[2]), "height": int(game_window_rect[3])})
        except cv2.error as e:
            logging.error(f'Could not grab the image')
            logging.error(e)
            os._exit(1)

        if img is None:
            continue

        # force only 1 image in the queue (newest)
        while not q.empty():
            q.get_nowait()

        q.put_nowait(img)
        q.join()


def cv2_process(q):
    global _show_cv2, game_window_rect

    fps = FPS()
    font = cv2.FONT_HERSHEY_SIMPLEX

    # mouse = MouseControls()

    while True:
        if not q.empty():
            img = q.get_nowait()
            q.task_done()

            # DO PROCESSING CODE HERE
            # i.e., inference, detect rects, paint stuff, log, etc.
            # <PROCESSING-CODE-GOES-HERE>

            # cv stuff
            if _show_cv2:
                img = cv2.putText(img, f"{fps():.2f}", (20, 120), font,
                                  1.7, (0, 255, 0), 7, cv2.LINE_AA)

                img = cv2.resize(img, (1280, 720))
                cv2.imshow("Captured & Processed image", img)
                cv2.waitKey(1)


def switch_shoot_state(triggered, hotkey):
    global _activated
    _activated = not _activated  # inverse value


keyboard.add_hotkey(ACTIVATION_HOTKEY, switch_shoot_state, args=('triggered', 'hotkey'))


if __name__ == "__main__":

    qq = multiprocessing.JoinableQueue()

    p1 = multiprocessing.Process(target=grab_process, args=(qq,))
    p2 = multiprocessing.Process(target=cv2_process, args=(qq,))

    p1.start()
    p2.start()
