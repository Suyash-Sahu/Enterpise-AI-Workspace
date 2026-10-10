"""
Calendar service (AMOF-X Phase 7): thin wrapper over GoogleCalendarClient,
parallel to how GoogleConnectorService wraps GmailClient -- same
token-fetch/401-refresh-retry shape, kept in its own file rather than folded
into google_connector_service.py so that file doesn't keep growing with
every new Google surface.
"""
from sqlalchemy.orm import Session
import requests

from app.connectors.google.calendar import GoogleCalendarClient
from app.services.token_service import TokenService


class CalendarService:

    @staticmethod
    def _calendar(
        db: Session,
        user_id: int,
    ) -> GoogleCalendarClient:

        token = TokenService.get_google_token(db, user_id=user_id)

        return GoogleCalendarClient(token)

    @staticmethod
    def list_events(
        db: Session,
        user_id: int,
        time_min: str,
        time_max: str,
        limit: int = 20,
    ):

        try:

            calendar = CalendarService._calendar(db, user_id)

            return calendar.list_events(time_min, time_max, limit)

        except requests.exceptions.HTTPError as e:

            if (
                e.response is not None
                and e.response.status_code == 401
            ):

                token = TokenService.force_refresh_google_token(db, user_id=user_id)

                calendar = GoogleCalendarClient(token)

                return calendar.list_events(time_min, time_max, limit)

            raise

    @staticmethod
    def get_event(
        db: Session,
        user_id: int,
        event_id: str,
    ):

        try:

            calendar = CalendarService._calendar(db, user_id)

            return calendar.get_event(event_id)

        except requests.exceptions.HTTPError as e:

            if (
                e.response is not None
                and e.response.status_code == 401
            ):

                token = TokenService.force_refresh_google_token(db, user_id=user_id)

                calendar = GoogleCalendarClient(token)

                return calendar.get_event(event_id)

            raise

    @staticmethod
    def create_event(
        db: Session,
        user_id: int,
        summary: str,
        start: str,
        end: str,
        description: str = "",
        attendees: list[str] | None = None,
        add_meet: bool = False,
    ):

        try:

            calendar = CalendarService._calendar(db, user_id)

            return calendar.create_event(summary, start, end, description, attendees, add_meet)

        except requests.exceptions.HTTPError as e:

            if (
                e.response is not None
                and e.response.status_code == 401
            ):

                token = TokenService.force_refresh_google_token(db, user_id=user_id)

                calendar = GoogleCalendarClient(token)

                return calendar.create_event(summary, start, end, description, attendees, add_meet)

            raise

    @staticmethod
    def update_event(
        db: Session,
        user_id: int,
        event_id: str,
        **fields,
    ):

        try:

            calendar = CalendarService._calendar(db, user_id)

            return calendar.update_event(event_id, **fields)

        except requests.exceptions.HTTPError as e:

            if (
                e.response is not None
                and e.response.status_code == 401
            ):

                token = TokenService.force_refresh_google_token(db, user_id=user_id)

                calendar = GoogleCalendarClient(token)

                return calendar.update_event(event_id, **fields)

            raise

    @staticmethod
    def check_availability(
        db: Session,
        user_id: int,
        time_min: str,
        time_max: str,
    ):

        try:

            calendar = CalendarService._calendar(db, user_id)

            return calendar.check_availability(time_min, time_max)

        except requests.exceptions.HTTPError as e:

            if (
                e.response is not None
                and e.response.status_code == 401
            ):

                token = TokenService.force_refresh_google_token(db, user_id=user_id)

                calendar = GoogleCalendarClient(token)

                return calendar.check_availability(time_min, time_max)

            raise
