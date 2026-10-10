import uuid

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class GoogleCalendarClient:
    """
    Mirrors GmailClient's structure exactly (session reuse, retry policy,
    bearer-token injection) -- same connector shape, different Google API.
    """

    BASE_URL = "https://www.googleapis.com/calendar/v3"

    TIMEOUT_SECONDS = 20

    # Same rationale as GmailClient: excludes POST from the retried methods,
    # so creating/updating an event is never silently duplicated by a retry.
    _RETRY_POLICY = Retry(
        total=3,
        connect=3,
        read=2,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        raise_on_status=False,
    )

    def __init__(
        self,
        access_token: str,
        pool_size: int = 10,
    ):

        self.access_token = access_token

        self._session = requests.Session()

        adapter = HTTPAdapter(
            max_retries=self._RETRY_POLICY,
            pool_connections=pool_size,
            pool_maxsize=pool_size,
        )
        self._session.mount("https://", adapter)

    # =====================================================
    # INTERNAL REQUEST
    # =====================================================

    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ):

        headers = kwargs.pop(
            "headers",
            {},
        )

        headers["Authorization"] = (
            f"Bearer {self.access_token}"
        )

        kwargs.setdefault("timeout", self.TIMEOUT_SECONDS)

        response = self._session.request(
            method=method,
            url=f"{self.BASE_URL}{endpoint}",
            headers=headers,
            **kwargs,
        )

        response.raise_for_status()

        if response.text.strip():

            return response.json()

        return {}

    # =====================================================
    # LIST EVENTS
    # =====================================================

    def list_events(
        self,
        time_min: str,
        time_max: str,
        max_results: int = 20,
    ):

        result = self._request(
            "GET",
            "/calendars/primary/events",
            params={
                "timeMin": time_min,
                "timeMax": time_max,
                "maxResults": max_results,
                "singleEvents": "true",
                "orderBy": "startTime",
            },
        )

        return result.get(
            "items",
            [],
        )

    # =====================================================
    # GET EVENT
    # =====================================================

    def get_event(
        self,
        event_id: str,
    ):

        return self._request(
            "GET",
            f"/calendars/primary/events/{event_id}",
        )

    # =====================================================
    # CREATE EVENT
    # =====================================================

    def create_event(
        self,
        summary: str,
        start: str,
        end: str,
        description: str = "",
        attendees: list[str] | None = None,
        add_meet: bool = False,
    ):

        body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start},
            "end": {"dateTime": end},
        }

        if attendees:
            body["attendees"] = [{"email": a} for a in attendees]

        params = {}
        if add_meet:
            body["conferenceData"] = {
                "createRequest": {
                    "requestId": str(uuid.uuid4()),
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }
            params["conferenceDataVersion"] = 1

        return self._request(
            "POST",
            "/calendars/primary/events",
            json=body,
            params=params,
        )

    # =====================================================
    # UPDATE EVENT
    # =====================================================

    def update_event(
        self,
        event_id: str,
        **fields,
    ):

        body = {}

        if "summary" in fields:
            body["summary"] = fields["summary"]

        if "description" in fields:
            body["description"] = fields["description"]

        if "start" in fields:
            body["start"] = {"dateTime": fields["start"]}

        if "end" in fields:
            body["end"] = {"dateTime": fields["end"]}

        return self._request(
            "PATCH",
            f"/calendars/primary/events/{event_id}",
            json=body,
        )

    # =====================================================
    # FREE/BUSY
    # =====================================================

    def check_availability(
        self,
        time_min: str,
        time_max: str,
    ):

        result = self._request(
            "POST",
            "/freeBusy",
            json={
                "timeMin": time_min,
                "timeMax": time_max,
                "items": [{"id": "primary"}],
            },
        )

        return (
            result.get("calendars", {})
            .get("primary", {})
            .get("busy", [])
        )
