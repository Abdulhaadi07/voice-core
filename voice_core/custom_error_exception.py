from rest_framework.exceptions import (
    APIException,
    ParseError,
    ValidationError,
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    NotFound,
    MethodNotAllowed,
    NotAcceptable,
    UnsupportedMediaType,
    Throttled
)


# ----- Custom 5xx Exceptions -----
class BadGateway(APIException):
    status_code = 502
    default_detail = "Upstream service error."
    default_code = "bad_gateway"


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = "Service temporarily unavailable."
    default_code = "service_unavailable"


class GatewayTimeout(APIException):
    status_code = 504
    default_detail = "Gateway timeout."
    default_code = "gateway_timeout"


class NotImplementedAPI(APIException):
    status_code = 501
    default_detail = "This feature is not implemented."
    default_code = "not_implemented"


# ----- Status Code Mapper -----
def raise_custom_drf_exception(status_code: int, detail: str = None) -> APIException:
    """
    Map an HTTP status code to an appropriate DRF exception.
    Falls back to APIException for unknown status codes.
    """
    exception_map = {
        400: ParseError(detail=detail) if detail else ParseError(),
        401: AuthenticationFailed(detail=detail) if detail else AuthenticationFailed(),
        403: PermissionDenied(detail=detail) if detail else PermissionDenied(),
        404: NotFound(detail=detail) if detail else NotFound(),
        405: MethodNotAllowed("method", detail=detail) if detail else MethodNotAllowed("method"),
        406: NotAcceptable(detail=detail) if detail else NotAcceptable(),
        415: UnsupportedMediaType("media_type", detail=detail) if detail else UnsupportedMediaType("media_type"),
        429: Throttled(wait=None, detail=detail) if detail else Throttled(wait=None),

        # Server errors
        500: APIException(detail=detail) if detail else APIException(),
        501: NotImplementedAPI(detail=detail) if detail else NotImplementedAPI(),
        502: BadGateway(detail=detail) if detail else BadGateway(),
        503: ServiceUnavailable(detail=detail) if detail else ServiceUnavailable(),
        504: GatewayTimeout(detail=detail) if detail else GatewayTimeout(),
    }

    return exception_map.get(status_code, APIException(detail=detail) if detail else APIException())
