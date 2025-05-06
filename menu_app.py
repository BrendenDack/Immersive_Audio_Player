import os
import curses
import subprocess
import time
from gpiozero import Button
import gpiozero as gpio
from gpiozero.pins.mock import MockFactory
from gpiozero.exc import GPIOZeroError
import threading
from stt import start_voice_recognition, play_song
from calibrateUserProfile import run_calibration

# Mock pins for testing - Remove if you have real buttons to test with
gpio.Device.pin_factory = MockFactory()

# GPIO buttons (optional for testing on hardware)
try:
    # Claim all button GPIOs
    SELECT_BUTTON =  Button(26, pull_up=True, bounce_time=0.1)
    BACK_BUTTON =  Button(16, pull_up=True, bounce_time=0.1)
    UP_BUTTON =  Button(4, pull_up=True, bounce_time=0.1)
    RIGHT_BUTTON =  Button(22, pull_up=True, bounce_time=0.1)
    DOWN_BUTTON =  Button(20, pull_up=True, bounce_time=0.1)
    LEFT_BUTTON =  Button(21, pull_up=True, bounce_time=0.1)
    VOLUME_UP =  Button(23, pull_up=True, bounce_time=0.1)
    VOLUME_DOWN =  Button(24, pull_up=True, bounce_time=0.1)
except GPIOZeroError:
    SELECT_BUTTON = BACK_BUTTON = UP_BUTTON = RIGHT_BUTTON = DOWN_BUTTON = LEFT_BUTTON = VOLUME_DOWN = VOLUME_UP = None
    print(f"Buttons init Failed. Could not claim Buttons.")
    time.sleep(3)

# Menu definitions with labels, targets, and actions
menus = {
    "main": {
        "title": "Main Menu",
        "options": [
            {"label": "Library", "target": "submenu_a", "action_type" : "dynamic"},
            {"label": "Settings", "target": "submenu_b"},
            {"label": "Player", "target": "submenu_c"},
        ]
    },
    "submenu_a": {
        "title": "Library",
        "options": [
            {"label": "Songs", "target": None},
            {"label": "Back", "target": "back"}
        ]
    },
    "submenu_b": {
        "title": "Settings",
        "options": [
            {"label": "Change Time", "target": None, "action" : "date", "action_type" : "shell"},
            {"label": "Change Profile", "target": None, "action" : ""},
            {"label": "Back", "target": "back"}
        ]
    },
    "submenu_c": {
        "title": "Music Player",
        "options": [
            {"label": "Current Track", "target": None},
            {"label": "Time Remaining", "target": None},
            {"label": "Back", "target": "back"}
        ]
    }
}

def load_music_files(page=0):
    global all_music_files, current_page

    music_folder = "Music"
    try:
        files = os.listdir(music_folder)
        mp3s = sorted([f for f in files if f.lower().endswith(".mp3")])
        all_music_files = mp3s
        current_page = page

        start = page * items_per_page
        end = start + items_per_page
        current_files = mp3s[start:end]

        options = [{"label": f, "target": None, "action": f"echo Playing {f}", "action_type": "shell"} for f in current_files]

        if page > 0:
            options.append({"label": "Previous Page", "target": "prev_page"})
        if end < len(mp3s):
            options.append({"label": "Next Page", "target": "next_page"})

        options.append({"label": "Back", "target": "back"})

        menus["submenu_a"]["options"] = options
    except Exception as e:
        menus["submenu_a"]["options"] = [
            {"label": f"Error loading files: {e}", "target": "back"},
            {"label": "Back", "target": "back"}
        ]



def start_voice():
    global recognition_running, recognition_thread

    if recognition_running:
        print("this button is working upon press, ignoring presses")
        return
    
    def recognition_wrapper():
        global recognition_running
        recognition_running = True
        try:
            start_voice_recognition()
        except Exception as e:
            print(f"voice recognition crash {e}")
        finally: 
            recognition_running = False
            print("voice recognition ended")
    #start_voice_recognition()
    #Run the voice recognition in a seperate thread
    recognition_thread = threading.Thread(target=recognition_wrapper)
    recognition_thread.daemon=True # Daemonize the thread to allow it to exit with the main program
    recognition_thread.start() # Start the recognition process

def clear_console():
    os.system('cls' if os.name == 'nt' else 'clear')

function_dictionary = {
    # Default setup for function dictionary. Just add your name and function to use it in the submenus
    "default_function" : clear_console, 
    "start_voice" : start_voice,
    "play_song" : play_song
}

# State
menu_stack = ["main"]
current_index = 0
up_pressed = down_pressed = select_pressed = back_pressed = False
current_page = 0
items_per_page = 5
all_music_files = []


def handle_selection(stdscr, selected_option, h, w):
    global current_index

    label = selected_option["label"]
    target = selected_option.get("target")
    action = selected_option.get("action")
    action_type = selected_option.get("action_type", "shell")

    if target == "back":
        if len(menu_stack) > 1:
            menu_stack.pop()
            current_index = 0
    elif target == "next_page":
        load_music_files(current_page + 1)
        current_index = 0
    elif target == "prev_page":
        load_music_files(current_page - 1)
        current_index = 0
    elif target and target in menus:
    # Check if we need to generate the submenu dynamically
        if selected_option.get("action_type") == "dynamic" and target == "submenu_a":
            load_music_files(page=0)
        menu_stack.append(target)
        current_index = 0
    elif action:
        if action_type == "shell":
            try:
                result = subprocess.run(action, shell=True, text=True, capture_output=True)
                output = result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
            except Exception as e:
                output = f"Shell Error: {e}"
        elif action_type == "python":
            func = function_dictionary.get(action)
            if func:
                try:
                    output = func()
                except Exception as e:
                    output = f"Python Error: {e}"
            else:
                output = f"Function '{action}' not found"
        else:
            output = f"Unknown action type: {action_type}"

        stdscr.clear()
        lines = str(output).split("\n")
        for i, line in enumerate(lines):
            stdscr.addstr(h // 2 - len(lines) // 2 + i, w // 2 - len(line) // 2, line)
        stdscr.refresh()
        time.sleep(2)
    else:
        stdscr.clear()
        message = f"You selected: {label}"
        stdscr.addstr(h // 2, w // 2 - len(message) // 2, message)
        stdscr.refresh()
        time.sleep(1)



def draw_menu(stdscr):
    global current_index, up_pressed, down_pressed, select_pressed, back_pressed

    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)
    curses.start_color()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN)

    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()

        current_menu_key = menu_stack[-1]
        current_menu = menus[current_menu_key]
        options = current_menu["options"]
        title = current_menu["title"]

        stdscr.addstr(1, w // 2 - len(title) // 2, title, curses.A_BOLD)

        for idx, option in enumerate(options):
            label = option["label"]
            x = w // 2 - len(label) // 2
            y = h // 2 - len(options) // 2 + idx
            if idx == current_index:
                stdscr.attron(curses.color_pair(1))
                stdscr.addstr(y, x, label)
                stdscr.attroff(curses.color_pair(1))
            else:
                stdscr.addstr(y, x, label)

        stdscr.refresh()

        try:
            key = stdscr.getch()
        except Exception:
            key = -1

        if key == curses.KEY_UP:
            current_index = (current_index - 1) % len(options)
        elif key == curses.KEY_DOWN:
            current_index = (current_index + 1) % len(options)
        elif key in [curses.KEY_ENTER, ord('\n'), ord('\r')]:
            selected_option = options[current_index]
            handle_selection(stdscr, selected_option, h, w)
        elif key in [curses.KEY_BACKSPACE, 127]:
            handle_selection(stdscr, {"label": "Back", "target": "back"}, h, w)

        # GPIO button input
        if UP_BUTTON and UP_BUTTON.is_pressed and not up_pressed:
            current_index = (current_index - 1) % len(options)
            up_pressed = True
        elif UP_BUTTON and not UP_BUTTON.is_pressed:
            up_pressed = False

        if DOWN_BUTTON and DOWN_BUTTON.is_pressed and not down_pressed:
            current_index = (current_index + 1) % len(options)
            down_pressed = True
        elif DOWN_BUTTON and not DOWN_BUTTON.is_pressed:
            down_pressed = False

        if SELECT_BUTTON and SELECT_BUTTON.is_pressed and not select_pressed:
            selected_option = options[current_index]
            handle_selection(stdscr, selected_option, h, w)
            select_pressed = True
        elif SELECT_BUTTON and not SELECT_BUTTON.is_pressed:
            select_pressed = False

        if BACK_BUTTON.is_pressed and not back_pressed:
            handle_selection(stdscr, "Back", h, w)
            back_pressed = True
        elif back_pressed and not BACK_BUTTON.is_pressed:
            back_pressed = False
        
        time.sleep(0.05)

def main():
    try:
        curses.wrapper(draw_menu)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
