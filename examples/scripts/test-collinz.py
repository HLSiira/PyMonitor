
from queue import Empty
import threading
import logging
import multiprocessing
from multiprocessing import Queue
from datetime import datetime

import requests
from requests import Timeout, RequestException


URL = "http://167.99.6.253:5000/"
PROCESSES = 6
THREADS_PER_PROCESS = 200
REQUESTS_PER_THREAD = 2
SECONDS_BEFORE_TIMEOUT = None


from threading import Lock


class DualCounter:

    def __init__(self):
        self.successes = 0
        self.failures = 0
        self.lock = Lock()

    def success(self):
        with self.lock:
            self.successes += 1

    def failure(self):
        with self.lock:
            self.failures += 1

    @property
    def count(self):
        with self.lock:
            return self.successes, self.failures



def request(counter):
    global REQUESTS_PER_THREAD, SECONDS_BEFORE_TIMEOUT
    for _ in range(REQUESTS_PER_THREAD):
        try:
            requests.get(url=URL, timeout=SECONDS_BEFORE_TIMEOUT)
            counter.success()
        except Timeout as exc:
            counter.failure()
            logging.warning("Request Timeout: %s", exc)
        except RequestException as exc:
            counter.failure()
            logging.warning("Request Failed %s", exc)
        except Exception as exc:
            counter.failure()
            logging.warning("Something Else Failed %s", exc)


def process_context(results_queue: Queue):
    global URL, THREADS_PER_PROCESS

    counter = DualCounter()

    threads = [threading.Thread(target=request, args=(counter,), daemon=True) for _ in range(THREADS_PER_PROCESS)]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    results_queue.put(counter.count)


def main():
    global PROCESSES

    results_queue = Queue()
    processes = [multiprocessing.Process(target=process_context, args=(results_queue,), daemon=True) for _ in range(PROCESSES)]

    for p in processes:
        p.start()

    start_time = datetime.now()

    for p in processes:
        p.join()

    time_delta = datetime.now() - start_time

    results = []
    while True:
        try:
            results.append(results_queue.get(block=False))
        except Empty:
            break

    total_successes = 0
    total_failed = 0
    for s, f in results:
        total_successes += s
        total_failed += f
    
    logging.info("Total Processes:                %s", PROCESSES)
    logging.info("Threads per Process:            %s", THREADS_PER_PROCESS)
    logging.info("Requests per Thread:            %s\n", REQUESTS_PER_THREAD)
    logging.info("Total Requests Attempted:       %s", PROCESSES * THREADS_PER_PROCESS * REQUESTS_PER_THREAD)
    logging.info("Total Successful Requests:      %s", total_successes)
    logging.info("Total Failed Requests:          %s", total_failed)
    logging.info("Total Seconds:                  %s", time_delta.seconds)
    logging.info("Successful Requests per Second: %s", (total_successes/time_delta.seconds))
    logging.info("Failure Percentage:             %s", (total_failed/(PROCESSES * THREADS_PER_PROCESS * REQUESTS_PER_THREAD)) * 100)

if __name__ == "__main__":
    logging.getLogger().setLevel("INFO")
    main()

