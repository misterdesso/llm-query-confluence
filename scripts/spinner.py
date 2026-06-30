import sys
import time
import threading
import itertools

class Spinner:
    def __init__(self, message="Working"):
        self.spinner = itertools.cycle(['-', '\\', '|', '/'])
        self.message = message
        self.stop_running = threading.Event()
        self.thread = None

    def spin(self):
        while not self.stop_running.is_set():
            sys.stdout.write(f'\r{self.message} {next(self.spinner)}')
            sys.stdout.flush()
            time.sleep(0.1)
        sys.stdout.write('\r\033[K')  # Clear the line
        sys.stdout.flush()

    def start(self):
        self.stop_running.clear()
        self.thread = threading.Thread(target=self.spin)
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.stop_running.set()
        if self.thread:
            self.thread.join()
