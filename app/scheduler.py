import threading

import schedule


class Scheduler(threading.Thread):
    def __init__(self, delay=1):
        self.delay = delay

        self.event = threading.Event()
        threading.Thread.__init__(self)

    def run(self):
        while not self.event.is_set():
            schedule.run_pending()
            self.event.wait(self.delay)

    def stop(self):
        self.event.set()
