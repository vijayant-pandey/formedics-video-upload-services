from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from .logging_config import get_logger


logger = get_logger('exception_handler')

def create_global_exception_handler(service_name: str = 'api'):
    """
    Create a global exception handler for a FastAPI app.

    This handler:
    - Catches all unhandled exceptions
    - Logs full error context with correlation ID
    - Returns a sanitized error response to clients
    - Includes correlation ID in response for debugging

    Args:
        service_name: Name of the service for logging context

    Returns:
        Async function that handles exceptions

    Usage:
        from common.exception_handlers import create_global_exception_handler

        app = FastAPI()

        @app.exception_handler(Exception)
        async def global_exception_handler(request, exc):
            handler = create_global_exception_handler('my_service')
            return await handler(request, exc)
    """

    async def handler(request: Request, exc: Exception):
        correlation_id = getattr(request.state, 'correlation_id', 'unknown')

        if isinstance(exc, HTTPException):
            logger.warning(
                'HTTP exception',
                service=service_name,
                correlation_id=correlation_id,
                path=request.url.path,
                method=request.method,
                query_params=dict(request.query_params),
                status_code=exc.status_code,
                detail=exc.detail,
            )

            return JSONResponse(
                status_code=exc.status_code,
                content={
                    'error': exc.detail,
                    'correlation_id': correlation_id,
                },
                headers={'X-Correlation-ID': correlation_id}
            )
        else:
            logger.error(
                'Unhandled exception',
                service=service_name,
                correlation_id=correlation_id,
                path=request.url.path,
                method=request.method,
                query_params=dict(request.query_params),
                exception_type=type(exc).__name__,
                exception_message=str(exc),
            )

            return JSONResponse(
                status_code=500,
                content={
                    'error': 'Internal server error',
                    'correlation_id': correlation_id,
                },
                headers={'X-Correlation-ID': correlation_id}
            )

    return handler


def setup_exception_handlers(app, service_name: str = 'api'):
    """
    Setup all exception handlers for a FastAPI app.

    This is a convenience function that registers the global exception handler.

    Args:
        app: FastAPI application instance
        service_name: Name of the service for logging context

    Usage:
        from common.exception_handlers import setup_exception_handlers

        app = FastAPI()
        setup_exception_handlers(app, 'iterable')
    """

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        handler = create_global_exception_handler(service_name)
        return await handler(request, exc)
