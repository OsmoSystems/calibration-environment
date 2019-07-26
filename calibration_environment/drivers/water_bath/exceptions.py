class InvalidResponse(ValueError):
    # Error class used when we can't interpret the response from the bath
    pass


class ErrorResponse(ValueError):
    # Error class used when we get an Error response from the bath
    pass


class PrecisionMismatch(ValueError):
    # Error class used when the bath's precision doesn't match our REPORTING_PRECISION
    pass


class WaterBathStatusError(ValueError):
    # Used when the water bath indicates a warning or fault status
    pass
