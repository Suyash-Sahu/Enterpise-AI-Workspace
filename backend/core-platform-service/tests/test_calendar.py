"""
AMOF-X Phase 7: Calendar connector/API tests.

Same discipline as test_google_connector_data.py for Gmail/Drive: the
fixture user has no Google grant, so every real call must fail with a real
error (409 "not connected"), never fabricated event data.
"""
from unittest.mock import patch

import pytest

from app.connectors.google.exceptions import GoogleNotConnectedError
from app.services.calendar_service import CalendarService

API = "/api/v1/calendar"

TIME_MIN = "2026-09-15T00:00:00Z"
TIME_MAX = "2026-09-22T00:00:00Z"


def test_unconnected_user_gets_an_error_not_invented_events(auth_client):
    response = auth_client.get(f"{API}/events", params={"time_min": TIME_MIN, "time_max": TIME_MAX})
    assert response.status_code == 409
    assert "connect" in response.json()["detail"].lower()


def test_unconnected_user_cannot_create_an_event(auth_client):
    response = auth_client.post(
        f"{API}/events",
        json={"summary": "Sync", "start": TIME_MIN, "end": TIME_MAX},
    )
    assert response.status_code == 409


def test_unconnected_user_gets_an_error_on_availability(auth_client):
    response = auth_client.get(f"{API}/availability", params={"time_min": TIME_MIN, "time_max": TIME_MAX})
    assert response.status_code == 409


def test_list_events_forwards_real_client_results(auth_client, test_user):
    """
    With a token available (mocked past TokenService), the connector must
    forward whatever GoogleCalendarClient actually returns -- not fabricate
    a response of its own.
    """
    fake_events = [{"id": "evt_1", "summary": "Planning sync"}]

    with patch("app.services.calendar_service.TokenService.get_google_token", return_value="fake-token"), \
         patch("app.connectors.google.calendar.GoogleCalendarClient.list_events", return_value=fake_events):
        response = auth_client.get(f"{API}/events", params={"time_min": TIME_MIN, "time_max": TIME_MAX})

    assert response.status_code == 200
    assert response.json() == {"count": 1, "events": fake_events}


def test_create_event_passes_attendees_through_to_the_client(auth_client, test_user):
    with patch("app.services.calendar_service.TokenService.get_google_token", return_value="fake-token"), \
         patch("app.connectors.google.calendar.GoogleCalendarClient.create_event") as mock_create:
        mock_create.return_value = {"id": "evt_new"}
        response = auth_client.post(
            f"{API}/events",
            json={
                "summary": "Design review",
                "start": TIME_MIN,
                "end": TIME_MAX,
                "attendees": ["a@example.com", "b@example.com"],
            },
        )

    assert response.status_code == 201
    mock_create.assert_called_once_with(
        "Design review", TIME_MIN, TIME_MAX, "", ["a@example.com", "b@example.com"], False,
    )


def test_create_event_with_add_meet_requests_a_real_conference():
    """
    Regression: the frontend used to fabricate a `meet.google.com/<slug>` link
    that never resolved to a real meeting. `add_meet=True` must instead ask
    Google to create a real Hangouts Meet conference on the event.
    """
    from app.connectors.google.calendar import GoogleCalendarClient

    client = GoogleCalendarClient("fake-token")
    captured = {}

    class FakeResponse:
        text = "{}"

        def raise_for_status(self):
            pass

        def json(self):
            return {"id": "evt_new"}

    def fake_request(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    client._session.request = fake_request

    client.create_event("Sync", TIME_MIN, TIME_MAX, add_meet=True)

    assert captured["params"] == {"conferenceDataVersion": 1}
    conference = captured["json"]["conferenceData"]["createRequest"]
    assert conference["conferenceSolutionKey"] == {"type": "hangoutsMeet"}
    assert conference["requestId"]


def test_calendar_service_raises_not_connected_for_a_user_with_no_grant(db_session, test_user):
    with pytest.raises(GoogleNotConnectedError):
        CalendarService.list_events(db=db_session, user_id=999999, time_min=TIME_MIN, time_max=TIME_MAX)
