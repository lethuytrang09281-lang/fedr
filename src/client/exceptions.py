class EfrsbException(Exception):
    """Базовое исключение для ошибок, связанных с EFRSB API."""
    pass


class AuthenticationError(EfrsbException):
    """Исключение, возникающее при ошибке аутентификации."""
    pass


class RateLimitError(EfrsbException):
    """Исключение, возникающее при превышении лимита запросов."""
    pass


class ApiError(EfrsbException):
    """Исключение, возникающее при других ошибках API."""
    pass