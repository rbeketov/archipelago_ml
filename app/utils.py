import ssl
from requests import Response


def get_ws_url(ip, port):
    if not ip or not port:
        return None
    return f"wss://{ip}:{port}"


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


def make_ssl_context(sert_path, key_path):
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(sert_path, keyfile=key_path)
    return ssl_context

def none_unpack(tup, num):
    if tup is None:
        return tuple((None for i in range(num)))
    return tup