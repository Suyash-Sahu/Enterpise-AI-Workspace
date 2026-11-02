"""
Connector-specific exceptions.

"You have not connected a Google account" and "Google refused the call" are
different conditions with different fixes, but both used to surface as the same
generic 502. The UI cannot prompt a reconnect if it cannot tell them apart.
"""


class GoogleConnectorError(Exception):
    """Base class for connector failures."""


class GoogleNotConnectedError(GoogleConnectorError):
    """
    No active Google grant exists for this user.

    Raised before any call to Google is attempted, so it is never the result of
    an upstream failure.
    """

    def __init__(
        self,
        message: str = "No Google account is connected to this workspace user.",
    ) -> None:
        super().__init__(message)


class GoogleReauthRequiredError(GoogleConnectorError):
    """
    Google account needs reauthorization due to missing or revoked scopes.
    """

    def __init__(
        self,
        message: str = "Google account permissions require reauthorization. Please reconnect your account.",
        scope_required: str | None = None,
    ) -> None:
        self.scope_required = scope_required
        super().__init__(message)


class GoogleServiceDisabledError(GoogleConnectorError):
    """
    Google API service is disabled or not enabled in the Google Cloud Project.
    """

    def __init__(
        self,
        message: str = "The requested Google service is not enabled in your Google Cloud Project.",
    ) -> None:
        super().__init__(message)
