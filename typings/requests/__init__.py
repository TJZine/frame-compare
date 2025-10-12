class RequestException(Exception):
    pass


class HTTPError(RequestException):
    def __init__(self, *args, **kwargs):
        self.response = kwargs.get("response")
        super().__init__(*args)


class Response:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code
        self.text = ""
        self.content = b""
        self.headers = {}

    def json(self):
        return {}


class CookieJar(dict):
    def get_dict(self):
        return dict(self)


class Session:
    def __init__(self):
        self.cookies = CookieJar()

    def get(self, *args, **kwargs):
        return Response()

    def post(self, *args, **kwargs):
        return Response()

    def close(self) -> None:
        pass


def request(*args, **kwargs):
    return Response()
