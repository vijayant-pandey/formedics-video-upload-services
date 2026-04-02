import time
import uuid
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from .logging_config import get_logger


logger = get_logger('middleware')

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log all requests with timing and correlation IDs.

    This middleware:
    - Generates a unique correlation ID for each request
    - Logs request details (method, path, query params, client IP)
    - Measures and logs request duration
    - Adds correlation ID to response headers
    - Logs errors with full context

    Usage:
        from common.middleware import RequestLoggingMiddleware

        app = FastAPI()
        app.add_middleware(RequestLoggingMiddleware)
    """

    def __init__(self, app, service_name: str = 'api'):
        super().__init__(app)
        self.service_name = service_name

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get('X-Correlation-ID') or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        start_time = time.time()
        logger.info(
            'Incoming request',
            service=self.service_name,
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
            query_params=dict(request.query_params),
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get('user-agent'),
        )

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            logger.info(
                'Request completed',
                service=self.service_name,
                correlation_id=correlation_id,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
                path=request.url.path,
                method=request.method,
            )

            response.headers['X-Correlation-ID'] = correlation_id
            return response

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                'Request failed with unhandled exception',
                service=self.service_name,
                correlation_id=correlation_id,
                method=request.method,
                path=request.url.path,
                query_params=dict(request.query_params),
                duration_ms=round(duration_ms, 2),
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise
