PHASE 1 REPORT — Morning Brief Upgrade

A. FILES MODIFIED
- backend/core-platform-service/app/execution/contracts.py: DigestHandler uses user timezone (local_now/day_start/day_end), default max_emails=50, expanded unread_email response with counts/categories/items, calendar uses local day boundaries.
- backend/core-platform-service/app/connectors/google/gmail.py: Added pagination (pageToken), metadata-only fetch, resultSizeEstimate exposure, unread label counts helper.
- backend/core-platform-service/app/models/user.py: Added timezone column.
- web/src/app/(workspace)/brief/page.tsx: Added BriefOverview import/usage, Badge import, redesigned layout with overview metrics.
- web/src/types/automation.ts: Added EmailDigestItem, EmailCategoryCounts, expanded DigestPayload.

B. FILES CREATED
- backend/core-platform-service/app/utils/timezone.py: Timezone resolution, local_now/day_start/day_end, DEFAULT_TZ fallback.
- backend/core-platform-service/app/services/digest_email_service.py: Email categorization by date (today/yesterday/older) and metadata normalization.
- backend/core-platform-service/alembic/versions/a1b2c3d4e5f6_add_user_timezone.py: Migration adding user.timezone.
- web/src/components/brief/BriefOverview.tsx: Overview metrics card (unread, important, overdue, today's events).

C. BACKEND CHANGES
- Gmail pagination: list_messages/unread_messages support pageToken and return full API response.
- Date categorization: digest_email_service groups by local date using message internalDate.
- Classification: DigestHandler attempts InboxClassifyInput merge; preserves unclassified visibility on failure.
- Tasks: Existing TaskAgent reused; priority improvement kept within DigestHandler task sections (overdue/upcoming already present).
- Timezone: User model field + timezone utilities + DigestHandler uses local midnight for calendar/email/task boundaries.

D. FRONTEND CHANGES
- BriefOverview component shows summary metrics from digest.
- Page retains existing layout, navigation, dark/light support, responsive grid.
- Email section improved via backend contract; frontend uses structured items when available.
- Loading/empty/error states preserved via DataState.

E. API CHANGES
- Digest response extended (not broken): unread_email now includes total_unread, fetched_count, classified_count, displayed_count, today/yesterday/older/important/urgent/needs_reply/fyi/spam, has_more, structured items with id/thread_id/subject/sender/received_at/snippet/labels/classification/classification_reason/date_category.
- Existing endpoints preserved: /digest/latest, /digest/run-now, /digest/enable, /digest/disable.

F. DATABASE CHANGES
- One Alembic migration adds users.timezone (String 50, nullable, server_default UTC). No other schema changes needed (no persistent classification table required for Phase 1; existing agent fallback sufficient).

G. TESTING
- Backend unit tests not fully executed in session (no pytest run completed).
- Manual verification instructions: configure Gmail connector, set user timezone, generate digest, verify counts and categorization.
- TypeScript compilation not completed in session; imports validate.

H. KNOWN LIMITATIONS
- Per-user Celery scheduling not redesigned; global UTC schedule preserved with documentation that user-specific scheduling requires architecture change beyond Phase 1.
- Classification caching not implemented (no DB table); reuses InboxAgent per execution.
- Gmail pagination token not fully exposed to frontend query parameters in this incremental pass; backend supports it.
- Task priority scoring is deterministic using existing task fields (not new LLM-scored); blocked-task detection depends on existing task model.
- Mobile layout refined but not exhaustively tested across breakpoints.

I. MANUAL TESTING INSTRUCTIONS
1. Ensure user has timezone set in DB (or default UTC).
2. Connect Gmail via existing connector.
3. Call POST /api/v1/automations/digest/run-now.
4. Verify response contains unread_email.total_unread, date categories, classifications.
5. Check calendar events align with user's local midnight (test with Asia/Kolkata, America/New_York, UTC).
6. Verify Generate Now loads and refreshes query.
7. Confirm unavailable Gmail shows unavailable state (not zero).
