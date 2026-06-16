class WeirServiceError(Exception):
    pass


class DataNotFoundError(WeirServiceError):
    pass


class InvalidParameterError(WeirServiceError):
    pass


class InsufficientDataError(WeirServiceError):
    pass


class CalculationError(WeirServiceError):
    pass
