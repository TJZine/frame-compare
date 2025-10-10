class Response:
    def __init__(self, status_code: int = 200, *, json=None, text=None):
        self.status_code = status_code
        self.text = text if text is not None else ""
        self.headers = {}
        self._json_data = json if json is not None else {}

    def json(self):
        return self._json_data


class AsyncClient:
    async def get(self, *args, **kwargs):
        return Response()

    async def post(self, *args, **kwargs):
        return Response()

    async def aclose(self) -> None:
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass


class RequestError(Exception):
    pass


class Timeout:
    def __init__(self, *args, **kwargs):
        pass


class MockTransport:
    def __init__(self, handler):
        self.handler = handler

    def __call__(self, request):
        return self.handler(request)

    async def handle_async_request(self, request):
        return self.handler(request)


class BaseTransport:
    async def handle_async_request(self, request):
        return Response()
