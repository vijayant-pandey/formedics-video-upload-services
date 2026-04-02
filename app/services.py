class HealthService:
    """Service for handling health check operations"""

    def get_health_status(self) -> dict:
        """Return service health status"""
        return {'status': 'running'}
