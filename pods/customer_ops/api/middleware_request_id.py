import uuid
from starlette.middleware.base import BaseHTTPMiddleware
REQUEST_ID_HEADER = "x-request-id"

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        rid = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = rid
        resp = await call_next(request)
        resp.headers[REQUEST_ID_HEADER] = rid
        return resp