"""
Stage-1 detectors: high-precision, deterministic, zero-cost.

These exist to catch the cases where being wrong is unacceptable and the
evidence is unambiguous: a private key, a card number, a credentials blob.
They are deliberately tuned for *precision*, not recall. A regex that fires on
anything resembling a number would push every task to local execution and make
the router useless. Recall is the job of stages 2 and 3.

Checksum-bearing identifiers (card numbers, Aadhaar) are validated rather than
pattern-matched alone. A bare 16-digit regex matches order numbers, invoice ids
and timestamps; with Luhn it essentially only matches card numbers.

Distinct from the two existing redaction paths: app/execution/metrics.py masks
known dict keys before persistence, and app/core/logging_config.py masks log
lines. Both sanitise output after a decision has been made. This module
classifies free text *before* a routing decision, and returns a label.
"""

from __future__ import annotations

import re
from typing import Callable, Iterable, NamedTuple, Optional

from app.privacy.contracts import SensitivityLabel, Signal


class Detector(NamedTuple):
    name: str
    pattern: re.Pattern
    label: SensitivityLabel
    weight: float
    # Optional second-stage check on the matched text. Returning False discards
    # the match, which is how checksum validation suppresses false positives.
    validator: Optional[Callable[[str], bool]] = None


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


def luhn_valid(text: str) -> bool:
    """Standard Luhn mod-10 checksum, used by every major card network."""
    digits = _digits(text)
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    parity = len(digits) % 2
    for idx, ch in enumerate(digits):
        digit = int(ch)
        if idx % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


_VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)


def verhoeff_valid(text: str) -> bool:
    """
    Verhoeff checksum. Aadhaar numbers carry one; plain 12-digit strings
    (timestamps, ids) almost never do, so this removes most false positives.
    Aadhaar numbers also never begin with 0 or 1.
    """
    digits = _digits(text)
    if len(digits) != 12 or digits[0] in "01":
        return False
    check = 0
    for idx, ch in enumerate(reversed(digits)):
        check = _VERHOEFF_D[check][_VERHOEFF_P[idx % 8][int(ch)]]
    return check == 0


# --- Detector catalogue -----------------------------------------------------
#
# RESTRICTED: live credential material. Leaking one is not just a privacy
#   violation, it's an ongoing compromise -- whoever has it can act as the
#   victim. Never cloud-eligible under any override (see
#   app/privacy/router.py::allowed_placements).
# CONFIDENTIAL: regulated identifiers and regulated subject matter. Leaking
#   one is a reportable incident, so these are treated as absolute rather
#   than weighed, but the exposure is disclosure, not impersonation.
# INTERNAL: organisationally private but not regulated. A softer signal that
#   still keeps a task local under the default policy.

DETECTORS = (
    # --- Secrets and credentials (RESTRICTED, AMOF-X Phase 3) ---
    Detector(
        "private_key_block",
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"),
        SensitivityLabel.RESTRICTED,
        1.0,
    ),
    Detector(
        "aws_access_key",
        re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        SensitivityLabel.RESTRICTED,
        1.0,
    ),
    Detector(
        "openai_style_key",
        re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"),
        SensitivityLabel.RESTRICTED,
        1.0,
    ),
    Detector(
        "github_token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
        SensitivityLabel.RESTRICTED,
        1.0,
    ),
    Detector(
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
        SensitivityLabel.RESTRICTED,
        1.0,
    ),
    Detector(
        "password_assignment",
        re.compile(
            r"(?i)\b(?:password|passwd|secret|api[_\-]?key|client[_\-]?secret"
            r"|access[_\-]?token)\s*[:=]\s*[\"']?[^\s\"']{6,}"
        ),
        SensitivityLabel.RESTRICTED,
        1.0,
    ),
    Detector(
        "db_connection_string",
        re.compile(
            r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)"
            r"://[^\s]*:[^\s]*@[^\s]+"
        ),
        SensitivityLabel.RESTRICTED,
        1.0,
    ),
    # --- Regulated personal identifiers ---
    Detector(
        "payment_card",
        re.compile(r"\b(?:\d[ \-]?){13,19}\b"),
        SensitivityLabel.CONFIDENTIAL,
        1.0,
        luhn_valid,
    ),
    Detector(
        "aadhaar",
        re.compile(r"\b\d{4}[ \-]?\d{4}[ \-]?\d{4}\b"),
        SensitivityLabel.CONFIDENTIAL,
        1.0,
        verhoeff_valid,
    ),
    Detector(
        "india_pan",
        re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
        SensitivityLabel.CONFIDENTIAL,
        0.9,
    ),
    Detector(
        "us_ssn",
        # Excludes structurally invalid ranges (000/666/9xx area, 00 group,
        # 0000 serial), which is what separates an SSN from a formatted id.
        re.compile(r"\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b"),
        SensitivityLabel.CONFIDENTIAL,
        1.0,
    ),
    Detector(
        "iban",
        re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
        SensitivityLabel.CONFIDENTIAL,
        0.85,
    ),
    Detector(
        "passport",
        re.compile(r"(?i)\bpassport\s*(?:no\.?|number|#)?\s*[:\-]?\s*[A-Z0-9]{6,9}\b"),
        SensitivityLabel.CONFIDENTIAL,
        0.9,
    ),
    # --- Regulated subject matter ---
    Detector(
        "health_record",
        re.compile(
            r"(?i)\b(?:diagnos(?:is|ed)|prognosis|medical record"
            r"|patient (?:id|name|chart)|prescription|blood (?:type|group)"
            r"|HIV|oncolog|psychiatric)\b"
        ),
        SensitivityLabel.CONFIDENTIAL,
        0.8,
    ),
    Detector(
        "compensation",
        re.compile(
            r"(?i)\b(?:salary|payroll|compensation|bonus|equity grant|stock option"
            r"|severance|appraisal rating)\b"
        ),
        SensitivityLabel.CONFIDENTIAL,
        0.8,
    ),
    Detector(
        "legal_privileged",
        re.compile(
            r"(?i)\b(?:attorney[- ]client|privileged and confidential"
            r"|litigation hold|non[- ]disclosure agreement|due diligence"
            r"|merger|acquisition target)\b"
        ),
        SensitivityLabel.CONFIDENTIAL,
        0.8,
    ),
    # --- Organisationally internal ---
    Detector(
        "email_address",
        re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),
        SensitivityLabel.INTERNAL,
        0.6,
    ),
    Detector(
        "private_ip",
        re.compile(
            r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))"
            r"\.\d{1,3}\.\d{1,3}\b"
        ),
        SensitivityLabel.INTERNAL,
        0.6,
    ),
    Detector(
        "internal_marker",
        re.compile(
            # "internal(?:ly)?" catches both the adjective ("internal-only
            # doc") and the adverb ("moved the date internally") -- the
            # original pattern matched only the adjective form and missed
            # every naturally-phrased adverbial sentence, which is how it
            # stayed silent on real internal content during the v2 corpus
            # evaluation (see privacy_labeling_rubric.md's int_ctx templates).
            r"(?i)\b(?:internal(?:ly|[- ]only)?|do not distribute"
            r"|company confidential|proprietary|trade secret|classified)\b"
        ),
        SensitivityLabel.INTERNAL,
        0.7,
    ),
    Detector(
        # Pre-disclosure secrecy framing: an embargo, a hold on external
        # comms, or "not yet public" language. High precision -- this
        # vocabulary is essentially never used about content that is
        # actually meant to be public, which is exactly the failure mode the
        # v2 corpus surfaced: an embedding stage can find a pre-announcement
        # email topically similar to a real public announcement and miss
        # that the whole point of the email is that it ISN'T public yet.
        "embargo_secrecy",
        re.compile(
            r"(?i)\b(?:press embargo|under embargo|embargo lifts"
            r"|hold (?:all )?external comms|not yet (?:public|announced)"
            r"|do not share.{0,40}?(?:externally|outside the team)"
            r"|outside the team\b.{0,30}?\b(?:until|before)"
            r"|before (?:it'?s|it is|this is) announced)\b"
        ),
        SensitivityLabel.INTERNAL,
        0.7,
    ),
    Detector(
        "employee_record",
        re.compile(
            r"(?i)\b(?:employee (?:id|record|roster)|headcount"
            r"|performance review|termination|disciplinary)\b"
        ),
        SensitivityLabel.INTERNAL,
        0.6,
    ),
)


def scan(text: str, detectors: Iterable[Detector] = DETECTORS) -> list[Signal]:
    """
    Runs every detector over `text` and returns the signals that fired.

    Matched text is intentionally not returned, only its span, so that audit
    logs built from these signals never themselves contain the secret.
    """
    if not text:
        return []

    signals: list[Signal] = []
    for det in detectors:
        for match in det.pattern.finditer(text):
            if det.validator is not None and not det.validator(match.group(0)):
                continue
            signals.append(
                Signal(
                    detector=det.name,
                    label=det.label,
                    span=(match.start(), match.end()),
                    weight=det.weight,
                )
            )
    return signals
