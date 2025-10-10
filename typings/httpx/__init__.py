class Response:
    def __init__(self, status_code: int = 200):
        self.status_code = status_code
        self.text = ""
        self.headers = {}

    def json(self):
        return {}


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
