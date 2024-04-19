import threading
import time

import schedule


class Scheduler(threading.Thread):
    def __init__(self, delay=1):
        self.delay = delay
        threading.Thread.__init__(self)

    def run(self):
        while True:
            schedule.run_pending()
            time.sleep(self.delay)
