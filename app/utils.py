from requests import Response


def get_ws_url(ip, port):
    return f"ws://{ip}:{port}"


class HTTPStatusException(Exception):
    def __init__(self, res):
        self.res = res
        super().__init__(res)


def wrap_http_err(res: Response) -> Response:
    try:
        res.raise_for_status()
    except Exception:
        raise HTTPStatusException(res)

    return res


def start_all_threads(threads):
    for thread in threads:
        thread.start()


def stop_all_threads(threads):
    for thread in threads:
        thread.stop()

    for thread in threads:
        thread.join()