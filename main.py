# Import required grabber from available under utils/grabbers
from utils.grabbers.mss import Grabber

# Import FPS measurment utility
from utils.fps import FPS

# Import moust controls, keyboard controls & some helpers
from utils.controls.mouse.win32 import MouseControls
from utils.win32 import WinHelper
import keyboard

# Import custom (more precise) sleep implementation
from utils.time import sleep

# default stuff
import cv2
import multiprocessing


# CONFIG
GAME_WINDOW_TITLE = "some_game"  # aimlab_tb, FallGuys_client, Counter-Strike: Global Offensive - Direct3D 9, etc
ACTIVATION_HOTKEY = 58  # 58 = CAPS-LOCK
_show_cv2 = True

# used by the script
game_window_rect = WinHelper.GetWindowRect(GAME_WINDOW_TITLE, (8, 30, 16, 39))  # cut the borders
_activated = False


def grab_process(q):
    grabber = Grabber()

    while True:
        img = grabber.get_image({"left": int(game_window_rect[0]), "top": int(game_window_rect[1]), "width": int(game_window_rect[2]), "height": int(game_window_rect[3])})

        if img is None:
            continue

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
            # i.e. inference, detect rects, paint stuff, log, etc
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

    q = multiprocessing.JoinableQueue()

    p1 = multiprocessing.Process(target=grab_process, args=(q,))
    p2 = multiprocessing.Process(target=cv2_process, args=(q,))

    p1.start()
    p2.start()