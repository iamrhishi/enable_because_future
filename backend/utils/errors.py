"""
Custom exception classes for becauseFuture backend
"""


class BecauseFutureError(Exception):
    """Base exception for all becauseFuture errors"""
    def __init__(self, message: str, status_code: int = 500, error_code: str = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        super().__init__(self.message)


class ValidationError(BecauseFutureError):
    """Raised when input validation fails"""
    def __init__(self, message: str, field: str = None):
        self.field = field
        super().__init__(message, status_code=400, error_code='VALIDATION_ERROR')


class AuthenticationError(BecauseFutureError):
    """Raised when authentication fails"""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, status_code=401, error_code='AUTHENTICATION_ERROR')


class AuthorizationError(BecauseFutureError):
    """Raised when user is not authorized"""
    def __init__(self, message: str = "Not authorized"):
        super().__init__(message, status_code=403, error_code='AUTHORIZATION_ERROR')


class NotFoundError(BecauseFutureError):
    """Raised when resource is not found"""
    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, status_code=404, error_code='NOT_FOUND')


class DatabaseError(BecauseFutureError):
    """Raised when database operation fails"""
    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message, status_code=500, error_code='DATABASE_ERROR')


class ExternalServiceError(BecauseFutureError):
    """Raised when external service call fails"""
    def __init__(self, message: str = "External service error", service: str = None):
        self.service = service
        super().__init__(message, status_code=502, error_code='EXTERNAL_SERVICE_ERROR')

