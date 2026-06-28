from __future__ import annotations


class Bitrix24Error(Exception):
    def __init__(
        self,
        error_code: str,
        *,
        request_id: str | None = None,
        bitrix_method: str | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(error_code)
        self.error_code = error_code
        self.request_id = request_id
        self.bitrix_method = bitrix_method
        self.http_status = http_status


class Bitrix24ConfigurationError(Bitrix24Error):
    pass


class Bitrix24TransportError(Bitrix24Error):
    pass


class Bitrix24TimeoutError(Bitrix24Error):
    pass


class Bitrix24RateLimitError(Bitrix24Error):
    pass


class Bitrix24AuthError(Bitrix24Error):
    pass


class Bitrix24PermissionError(Bitrix24Error):
    pass


class Bitrix24ValidationError(Bitrix24Error):
    pass


class Bitrix24NotFoundError(Bitrix24Error):
    pass


class Bitrix24UnexpectedResponseError(Bitrix24Error):
    pass
