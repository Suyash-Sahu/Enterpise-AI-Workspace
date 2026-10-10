"""
Google OAuth endpoints and requested scopes.

Scope rationale — each entry must be justified by a feature that exists:

  email
      Identifies the connected account. `openid` and `profile` were dropped:
      the connector only reads `email` from the userinfo response, and the
      connector flow never consumes an id_token.

  drive.readonly
      Required, and genuinely the narrowest option for this feature set. The
      app browses, searches and ingests the user's *existing* Drive files for
      RAG indexing. `drive.file` only grants access to files the app itself
      created or the user explicitly picked, which cannot support browsing an
      existing Drive; `drive.metadata.readonly` returns no file content, which
      cannot support ingestion. Google offers nothing in between, so this stays
      broad by necessity rather than by oversight.

  gmail.readonly
      Reading messages, threads, labels, profile and search.

  gmail.compose
      Creating drafts, and sending. Replaces `gmail.send`, which is a strict
      subset: the draft endpoint calls the drafts API and was failing at
      runtime because `gmail.compose` was never requested. Listing both would
      be redundant.

  calendar.events
      AMOF-X Phase 7: list/get/create/update events. `calendar.events` grants
      only event CRUD, not calendar-list management (`calendar`) or
      settings (`calendar.settings.readonly`), neither of which any feature
      here uses.

  calendar.freebusy
      Phase 7's availability check (`check_availability`). The freebusy.query
      endpoint accepts this narrower scope instead of full `calendar`/
      `calendar.events` access, so it's requested on its own rather than
      folded into `calendar.events`.

Changing this list invalidates existing consent: connected accounts must
reconnect before Gmail, Drive, or Calendar calls will succeed again.
"""

SCOPES = [
    "email",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.freebusy",
]

# Scopes for signing in. Identity only: these establish who the user is and
# grant no access to their mail or files. Connector consent is a separate,
# later, explicit step with the broader SCOPES above.
IDENTITY_SCOPES = [
    "openid",
    "email",
    "profile",
]

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"

TOKEN_URL = "https://oauth2.googleapis.com/token"

USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
