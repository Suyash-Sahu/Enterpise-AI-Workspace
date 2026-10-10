"""
Synthetic privacy-sensitivity corpus generator.

Produces the v2 exemplar bank and evaluation set that replace Week 1's 51/24
hand-written seed files. Labels are assigned by the rules in
evaluation/datasets/privacy_labeling_rubric.md, applied here as data, not
decided per item while writing -- every label in the output traces to one of
the template's declared (label, signal_type) fields, fixed before any text
is rendered.

Why templates + Faker instead of hand-writing 300+ items
----------------------------------------------------------
Hand-writing 300 items is still one person's biased writing, just more of it.
This generator separates two things that used to be the same act:

  - TEMPLATE DESIGN (still human-authored, ~70 templates): what shape does a
    confidential finance email look like, structurally.
  - INSTANCE RENDERING (never human-authored): each template is instantiated
    6-9x with independently Faker-sampled fake names/companies/SSNs/card
    numbers/amounts and randomly chosen phrasing variants. No two rendered
    instances of the same template are identical text, and no rendered
    instance is something a person typed by hand.

The corpus's size is not just "more data" -- it is what makes a real
train/test split possible. With Week 1's 51/24 hand-written items there was no
way to split by anything other than "which file I happened to put it in."
Here, the split (see split_by_template()) is stratified BY TEMPLATE, not by
instance: every instance of a given template goes to the SAME side of the
split. Two instances of the same template differing only by a swapped name and
SSN are near-duplicates -- splitting them across train/test would leak
template-level structure across the boundary even with zero exact-text
overlap, which is precisely the failure "count files, check text overlap"
doesn't catch.

Provenance and PII: every name, company, SSN, card number, address and account
number below comes from `Faker`. None of it is a real person or organization.
See the rubric's Provenance section for the full statement.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Optional

from faker import Faker

SERVICE_ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = SERVICE_ROOT / "evaluation" / "datasets"

if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from app.privacy.patterns import verhoeff_valid  # noqa: E402

LABELS = ("public", "internal", "confidential")
SIGNAL_TYPES = ("explicit_identifier", "contextual", "surface_similar_benign")


# --------------------------------------------------------------------------
# Aadhaar generation: reuse the EXISTING validated Verhoeff checker rather
# than re-deriving the checksum algorithm. Brute-forcing the one check digit
# against a function that is already tested (tests/test_privacy_routing.py)
# is safer than a second, independent implementation of the same tables.
# --------------------------------------------------------------------------


def fake_aadhaar(rng: random.Random) -> str:
    prefix = str(rng.randint(2, 9)) + "".join(str(rng.randint(0, 9)) for _ in range(10))
    for check_digit in range(10):
        candidate = prefix + str(check_digit)
        if verhoeff_valid(candidate):
            return f"{candidate[0:4]} {candidate[4:8]} {candidate[8:12]}"
    raise AssertionError("no valid Verhoeff check digit found in 0-9; algorithm bug")


# --------------------------------------------------------------------------
# Entity pool: one dict per rendered instance, built once and reused across
# whichever subset of keys a given template's format string references.
# --------------------------------------------------------------------------

GREETINGS = ["Hi {name},", "Hello {name},", "{name} --", "Hey {name},"]
SIGNOFFS = ["Thanks,\n{sender}", "Best,\n{sender}", "Regards,\n{sender}", "-- {sender}"]
OPENERS = [
    "Quick update:",
    "Following up on this:",
    "Wanted to flag this:",
    "Sharing for visibility:",
]

# Audience/format framing, appended by render_template() to templates whose
# only variation would otherwise come from a small fixed-choice pool (a
# generic "explain how X works" doc_excerpt has no name/company/SSN to swap --
# every attempt would render byte-identical text without this). 10 options,
# comfortably above the largest n_instances used below, so the seen_texts
# dedup loop in generate_all() never starves for a distinct rendering.
REGISTERS = [
    "for a technical blog post",
    "for a new engineer's onboarding guide",
    "as a short FAQ answer",
    "for a conference talk outline",
    "in plain language for a general reader",
    "as a one-paragraph explainer",
    "for a developer newsletter",
    "as an introductory tutorial section",
    "for a public knowledge-base article",
    "in a casual, conversational tone",
]


def build_entities(fake: Faker, rng: random.Random) -> dict[str, str]:
    # GREETINGS/SIGNOFFS pool entries carry their own {name}/{sender}
    # placeholder syntax (e.g. "Hi {name},"). template.text.format(**entities)
    # runs exactly once, so if "greeting"/"signoff" were stored unresolved,
    # substituting {greeting} into the outer template inserts that literal
    # "{name}" text verbatim -- it never gets a second formatting pass. name
    # and sender must be picked first and used to resolve greeting/signoff
    # here, so what lands in `entities` is already-plain text.
    name = fake.name()
    sender = fake.first_name()
    return {
        "name": name,
        "name2": fake.name(),
        "sender": sender,
        "company": fake.company(),
        "competitor": fake.company(),
        "role": fake.job(),
        "department": rng.choice(
            ["Engineering", "Finance", "Legal", "People Ops", "Security", "Product", "Marketing"]
        ),
        "email": fake.company_email(),
        "ssn": fake.ssn(),
        "card": fake.credit_card_number(),
        "aadhaar": fake_aadhaar(rng),
        "iban": fake.iban(),
        "address": fake.address().replace("\n", ", "),
        "amount": f"${rng.randint(45, 420)},{rng.randint(0, 9)}{rng.randint(0, 9)}0",
        "salary": f"${rng.randint(78, 260)},000",
        "date": fake.date_between(start_date="-60d", end_date="+30d").isoformat(),
        "project": fake.catch_phrase().title().replace(" ", ""),
        "ticket_id": f"{rng.choice(['ENG', 'SEC', 'FIN', 'SUP'])}-{rng.randint(1000, 9999)}",
        "order_id": f"ORD-{rng.randint(100000, 999999)}",
        "invoice_id": f"INV-{rng.randint(10000, 99999)}",
        "internal_ip": f"10.0.{rng.randint(0, 255)}.{rng.randint(1, 254)}",
        "public_host": fake.domain_name(),
        "bs": fake.bs(),
        "catch_phrase": fake.catch_phrase(),
        "greeting": rng.choice(GREETINGS).format(name=name),
        "signoff": rng.choice(SIGNOFFS).format(sender=sender),
        "opener": rng.choice(OPENERS),
        "register": rng.choice(REGISTERS),
    }


# --------------------------------------------------------------------------
# Templates. Each declares its own label + signal_type per the rubric; the
# generator never infers a label from generated text.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Template:
    template_id: str
    content_type: str
    topic: str
    label: str
    signal_type: str
    text: str
    ambiguous: bool = False
    n_instances: int = 8


TEMPLATES: tuple[Template, ...] = (
    # =====================================================================
    # CONFIDENTIAL -- explicit_identifier
    # =====================================================================
    Template("conf_exp_01", "email", "finance", "confidential", "explicit_identifier",
              "{greeting}\n\n{opener} the refund for {name2} needs to go out today. Card on "
              "file is {card}, billing address {address}. Please process before EOD.\n\n{signoff}"),
    Template("conf_exp_02", "ticket", "finance", "confidential", "explicit_identifier",
              "[{ticket_id}] Customer {name2} disputes a charge on card {card}. Requesting "
              "chargeback review. SSN on file for identity verification: {ssn}."),
    Template("conf_exp_03", "doc_excerpt", "hr", "confidential", "explicit_identifier",
              "Employee record update -- {name}, {role}, {department}. SSN: {ssn}. "
              "Direct deposit account (IBAN): {iban}."),
    Template("conf_exp_04", "email", "security", "confidential", "explicit_identifier",
              "{greeting}\n\nRotate this immediately, it was committed to a public branch by "
              "mistake:\n\n-----BEGIN RSA PRIVATE KEY-----\nMIIEow{ticket_id}base64placeholder\n"
              "-----END RSA PRIVATE KEY-----\n\n{signoff}"),
    Template("conf_exp_05", "chat", "engineering", "confidential", "explicit_identifier",
              "can someone rotate this key, it leaked in a log line: sk-{ticket_id}abcdef123456789"),
    Template("conf_exp_06", "doc_excerpt", "legal", "confidential", "explicit_identifier",
              "KYC file for {name}: passport number {ticket_id}{ticket_id}, address {address}, "
              "account IBAN {iban}."),
    Template("conf_exp_07", "email", "engineering", "confidential", "explicit_identifier",
              "{greeting}\n\n{opener} the staging DB creds leaked: "
              "postgresql://svc_admin:S3cret!@db.internal.{public_host}:5432/prod -- rotate now.\n\n{signoff}"),
    Template("conf_exp_08", "doc_excerpt", "hr", "confidential", "explicit_identifier",
              "National ID verification -- {name}, Aadhaar {aadhaar}. Submitted for background "
              "check, department {department}."),
    # =====================================================================
    # CONFIDENTIAL -- contextual (no visible regulated identifier)
    # =====================================================================
    Template("conf_ctx_01", "email", "hr", "confidential", "contextual",
              "{greeting}\n\n{opener} {name}'s compensation review is done -- moving to {salary} "
              "base plus the retention bonus we discussed. Please keep this off the shared sheet "
              "until it's finalized.\n\n{signoff}"),
    Template("conf_ctx_02", "doc_excerpt", "legal", "confidential", "contextual",
              "Privileged and confidential -- attorney work product. Litigation strategy memo "
              "regarding the {name2} v. {company} matter. Do not forward outside counsel."),
    Template("conf_ctx_03", "meeting_note", "legal", "confidential", "contextual",
              "Notes from today's session with outside counsel on the proposed acquisition of "
              "{company}. Deal terms and valuation discussed are not to leave this room."),
    Template("conf_ctx_04", "doc_excerpt", "hr", "confidential", "contextual",
              "Performance improvement plan for {name}, {role}. Rating: below expectations. "
              "Disciplinary next step if no improvement by {date}."),
    Template("conf_ctx_05", "chat", "hr", "confidential", "contextual",
              "just left the room -- {name} disclosed a diagnosis and is requesting medical "
              "leave starting {date}. keeping this between us and HR for now."),
    Template("conf_ctx_06", "email", "legal", "confidential", "contextual",
              "{greeting}\n\n{opener} the settlement figure for the {name2} matter is {amount}. "
              "This has not been approved publicly and should stay within legal.\n\n{signoff}"),
    Template("conf_ctx_07", "meeting_note", "finance", "confidential", "contextual",
              "Board discussion: acquiring {competitor} at a valuation near {amount}k. Not yet "
              "disclosed to either company's employees."),
    Template("conf_ctx_08", "doc_excerpt", "hr", "confidential", "contextual",
              "Exit interview summary for {name}: cited compensation ({salary}) and management "
              "conflict with {name2} as primary reasons for departure."),
    Template("conf_ctx_09", "email", "hr", "confidential", "contextual",
              "{greeting}\n\nPlease treat this as sensitive -- {name}'s therapist has recommended "
              "reduced hours through {date}. Coordinating coverage without disclosing why.\n\n{signoff}",
              ambiguous=True),
    Template("conf_ctx_10", "doc_excerpt", "finance", "confidential", "contextual",
              "Internal audit finding: {department} overstated Q-close revenue by roughly "
              "{amount}. Draft disclosure pending legal review before any external statement.",
              ambiguous=True),
    # =====================================================================
    # INTERNAL -- contextual (organizationally private, not regulated)
    # =====================================================================
    Template("int_ctx_01", "doc_excerpt", "engineering", "internal", "contextual",
              "Architecture decision record: {project} will use event sourcing for the "
              "{department} service. Internal runbook and rollback steps attached."),
    Template("int_ctx_02", "chat", "engineering", "internal", "contextual",
              "heads up, the {ticket_id} rollout is paused -- staging is on {internal_ip}, "
              "not ready for prod yet"),
    Template("int_ctx_03", "meeting_note", "product", "internal", "contextual",
              "Roadmap sync: {project} slips to next quarter. Do not share the revised date "
              "outside the team until comms finalizes external messaging."),
    Template("int_ctx_04", "doc_excerpt", "security", "internal", "contextual",
              "Postmortem draft for the {date} outage on {internal_ip}. Root cause: unbounded "
              "retry loop in {department}'s queue consumer. Internal distribution only."),
    Template("int_ctx_05", "email", "product", "internal", "contextual",
              "{greeting}\n\n{opener} the {project} beta cohort feedback is in. Mixed on "
              "pricing -- keeping this internal until the pricing team finalizes the model.\n\n{signoff}"),
    Template("int_ctx_06", "doc_excerpt", "engineering", "internal", "contextual",
              "Internal onboarding checklist for new {department} hires: repo access, VPN "
              "setup, on-call rotation signup, {project} architecture walkthrough."),
    Template("int_ctx_07", "chat", "hr", "internal", "contextual",
              "{department} headcount for next quarter is 6 open reqs, pending finance sign-off "
              "-- don't post externally yet", n_instances=7),  # 'department' pool has 7 values
    Template("int_ctx_08", "meeting_note", "security", "internal", "contextual",
              "Threat model review for {project}: current mitigations documented in the "
              "internal wiki, not the public docs site."),
    Template("int_ctx_09", "doc_excerpt", "finance", "internal", "contextual",
              "Q{ticket_id} internal budget allocation by department: {department} received "
              "{amount} for tooling. Not for external distribution."),
    Template("int_ctx_10", "email", "marketing", "internal", "contextual",
              "{greeting}\n\n{opener} the {project} launch date moved to {date} internally. "
              "Please hold external comms until the press embargo lifts.\n\n{signoff}",
              ambiguous=True),
    Template("int_ctx_11", "chat", "product", "internal", "contextual",
              "reminder that the {project} pricing experiment results are internal-only until "
              "the readout next week", ambiguous=True),
    Template("int_ctx_12", "doc_excerpt", "engineering", "internal", "contextual",
              "Internal service dependency map: {department}'s API depends on the billing "
              "subsystem hosted at {internal_ip}. Do not publish this diagram externally."),
    # =====================================================================
    # INTERNAL -- directory-level identifier (not regulated)
    # =====================================================================
    Template("int_exp_01", "doc_excerpt", "hr", "internal", "explicit_identifier",
              "Employee directory entry: {name}, {role}, {department}. Desk location and "
              "extension attached for internal lookup."),
    Template("int_exp_02", "chat", "engineering", "internal", "explicit_identifier",
              "the {department} on-call this week is {name}, ping them directly for {ticket_id}"),
    Template("int_exp_03", "meeting_note", "product", "internal", "explicit_identifier",
              "Attendees: {name}, {name2}, {department} lead. Action items assigned per name "
              "below, tracked in {ticket_id}."),
    # =====================================================================
    # PUBLIC -- explanatory / documentation (no org-specific content)
    # =====================================================================
    Template("pub_exp_01", "doc_excerpt", "engineering", "public", "contextual",
              "Write a concise overview of how {catch_phrase} caching headers work in HTTP."),
    Template("pub_exp_02", "doc_excerpt", "engineering", "public", "contextual",
              "Explain how TLS certificate validation works when a browser connects to a "
              "public website."),
    Template("pub_exp_03", "doc_excerpt", "engineering", "public", "contextual",
              "Give an overview of how garbage collection works in a managed runtime."),
    Template("pub_exp_04", "doc_excerpt", "engineering", "public", "contextual",
              "Describe how a load balancer distributes incoming requests across a fleet of "
              "servers."),
    Template("pub_exp_05", "doc_excerpt", "engineering", "public", "contextual",
              "Explain how message queues decouple producers from consumers in a distributed "
              "system."),
    Template("pub_exp_06", "doc_excerpt", "security", "public", "contextual",
              "Summarize how OAuth refresh tokens differ from access tokens."),
    Template("pub_exp_07", "doc_excerpt", "engineering", "public", "contextual",
              "Give a general explanation of how database index structures speed up lookups."),
    Template("pub_exp_08", "doc_excerpt", "engineering", "public", "contextual",
              "Explain the CAP theorem with a plain-language example for a blog post."),
    Template("pub_exp_09", "doc_excerpt", "product", "public", "contextual",
              "Draft a public changelog entry announcing a new dark-mode setting."),
    Template("pub_exp_10", "doc_excerpt", "marketing", "public", "contextual",
              "Write marketing copy for a landing page about {bs}."),
    Template("pub_exp_11", "doc_excerpt", "engineering", "public", "contextual",
              "Write a tutorial explaining how to configure a database connection pool."),
    Template("pub_exp_12", "doc_excerpt", "engineering", "public", "contextual",
              "Explain hybrid search combining keyword and vector retrieval, for a technical "
              "blog audience."),
    Template("pub_exp_13", "doc_excerpt", "product", "public", "contextual",
              "Compose a public FAQ answer about supported browser versions for a web app."),
    Template("pub_exp_14", "doc_excerpt", "marketing", "public", "contextual",
              "Write a short public-facing description of a company that does {bs}."),
    Template("pub_exp_15", "doc_excerpt", "security", "public", "contextual",
              "Give a general, non-organization-specific explanation of how phishing emails "
              "typically try to trick a recipient."),
    Template("pub_exp_16", "doc_excerpt", "engineering", "public", "contextual",
              "Explain what a vector embedding is, in simple terms, for a general audience."),
    # =====================================================================
    # PUBLIC -- surface_similar_benign (deliberate hard negatives)
    # =====================================================================
    Template("pub_surf_01", "ticket", "product", "public", "surface_similar_benign",
              "[{ticket_id}] Customer asking about order {order_id} shipping status -- "
              "standard tracking request, no payment info needed to answer."),
    Template("pub_surf_02", "doc_excerpt", "marketing", "public", "surface_similar_benign",
              "Blog draft: 'How we think about {bs}' -- general commentary, no customer or "
              "employee data referenced."),
    Template("pub_surf_03", "doc_excerpt", "security", "public", "surface_similar_benign",
              "Security awareness training snippet: an example of what a phishing email "
              "looks like, using a fictional company name and a placeholder link, for "
              "training purposes only."),
    Template("pub_surf_04", "doc_excerpt", "engineering", "public", "surface_similar_benign",
              "Public API documentation example: a sample invoice payload "
              "({invoice_id}, line items, totals) using placeholder data for the docs site."),
    Template("pub_surf_05", "chat", "product", "public", "surface_similar_benign",
              "can you check order {order_id}, customer says it hasn't shipped yet"),
    Template("pub_surf_06", "doc_excerpt", "hr", "public", "surface_similar_benign",
              "General blog post: 'How salary negotiation works', with hypothetical example "
              "figures and no reference to any real employee."),
    Template("pub_surf_07", "doc_excerpt", "engineering", "public", "surface_similar_benign",
              "Public status-page incident note: brief service disruption, resolved, no "
              "customer data was affected."),
    Template("pub_surf_08", "doc_excerpt", "legal", "public", "surface_similar_benign",
              "Public terms-of-service excerpt describing, in general terms, how the company "
              "handles a customer data-deletion request."),
    Template("pub_surf_09", "email", "product", "public", "surface_similar_benign",
              "{greeting}\n\n{opener} the public roadmap page is now live at "
              "{public_host}/roadmap -- feel free to share externally.\n\n{signoff}",
              ambiguous=True),
    Template("pub_surf_10", "doc_excerpt", "finance", "public", "surface_similar_benign",
              "Public earnings-call transcript excerpt: forward-looking statement about "
              "market conditions, already disclosed to all investors.", ambiguous=True),
)

# There are more public templates (26) than confidential (18) or internal
# (18) above -- a consequence of the register-tag fix giving every public
# "explain how X works" template real entropy to reach its instance count,
# not a claim that public content is 26/18ths as common as confidential in a
# real enterprise. Left uncorrected, that template-count imbalance alone
# would make public the largest class in the corpus, which has nothing to do
# with sensitivity distribution and everything to do with how many distinct
# ways there are to phrase a generic technical explainer. Trimming public's
# per-template instance count keeps the three labels roughly balanced so
# per-class precision/recall/F1 in privacy_metrics.py have comparable
# support, which is the more standard evaluation practice than an
# unbalanced split driven by an accident of template count.
TEMPLATES = tuple(
    replace(t, n_instances=6) if t.label == "public" and t.n_instances == 8 else t
    for t in TEMPLATES
)


def validate_templates() -> None:
    for t in TEMPLATES:
        assert t.label in LABELS, f"{t.template_id}: bad label {t.label!r}"
        assert t.signal_type in SIGNAL_TYPES, f"{t.template_id}: bad signal_type {t.signal_type!r}"
    ids = [t.template_id for t in TEMPLATES]
    assert len(ids) == len(set(ids)), "duplicate template_id"


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


# Placeholders drawn from a pool this small cannot produce n_instances
# distinct renderings on their own (department has 7 options; greeting/
# signoff/opener are stylistic, not content-varying). A template whose
# placeholders are a subset of this set -- including the empty set -- gets a
# register tag appended so it actually varies; this is detected here rather
# than hand-flagged per template so the same fix covers any future template
# with the same shape.
_LOW_ENTROPY_ONLY = {"greeting", "signoff", "opener", "department"}


def _is_low_entropy(text: str) -> bool:
    placeholders = set(re.findall(r"\{(\w+)\}", text))
    return placeholders <= _LOW_ENTROPY_ONLY


def render_template(template: Template, fake: Faker, rng: random.Random) -> dict[str, Any]:
    entities = build_entities(fake, rng)
    text = template.text.format(**entities)
    if _is_low_entropy(template.text):
        text = f"{text} ({entities['register']})"
    return {
        "text": text,
        "label": template.label,
        "template_id": template.template_id,
        "content_type": template.content_type,
        "topic": template.topic,
        "signal_type": template.signal_type,
        "ambiguous": template.ambiguous,
    }


def generate_all(seed: int) -> list[dict[str, Any]]:
    validate_templates()
    fake = Faker()
    Faker.seed(seed)
    rng = random.Random(seed)

    items: list[dict[str, Any]] = []
    counter = 0
    for template in TEMPLATES:
        seen_texts: set[str] = set()
        attempts = 0
        produced = 0
        while produced < template.n_instances and attempts < template.n_instances * 5:
            attempts += 1
            row = render_template(template, fake, rng)
            if row["text"] in seen_texts:
                continue  # Faker collision (rare) -- retry rather than duplicate.
            seen_texts.add(row["text"])
            counter += 1
            row["item_id"] = f"pc_{counter:05d}"
            items.append(row)
            produced += 1
    return items


# --------------------------------------------------------------------------
# Stratified template-level split.
#
# The unit of the split is the TEMPLATE, not the instance: every rendered
# instance of a template goes to the same side, so no two near-duplicate
# instances of the same template end up on opposite sides of the train/test
# boundary. Stratified by (label, signal_type) so both splits get coverage
# of every bucket, not just whatever a plain random split happens to include.
# --------------------------------------------------------------------------


def split_by_template(
    items: list[dict[str, Any]],
    eval_fraction: float,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rng = random.Random(seed + 1)  # distinct stream from the entity rng

    by_bucket: dict[tuple[str, str], list[str]] = {}
    for t in TEMPLATES:
        by_bucket.setdefault((t.label, t.signal_type), []).append(t.template_id)

    eval_template_ids: set[str] = set()
    for tids in by_bucket.values():
        tids = sorted(tids)
        rng.shuffle(tids)
        n_eval = max(1, round(len(tids) * eval_fraction))
        eval_template_ids.update(tids[:n_eval])

    eval_items = [r for r in items if r["template_id"] in eval_template_ids]
    exemplar_items = [r for r in items if r["template_id"] not in eval_template_ids]
    return exemplar_items, eval_items


def assert_no_leakage(exemplar_items: list[dict], eval_items: list[dict]) -> None:
    ex_templates = {r["template_id"] for r in exemplar_items}
    ev_templates = {r["template_id"] for r in eval_items}
    overlap = ex_templates & ev_templates
    assert not overlap, f"template_id leakage across split: {overlap}"

    ex_texts = {r["text"] for r in exemplar_items}
    ev_texts = {r["text"] for r in eval_items}
    text_overlap = ex_texts & ev_texts
    assert not text_overlap, f"exact text leakage across split ({len(text_overlap)} items)"


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _summary(name: str, rows: list[dict]) -> None:
    print(f"\n{name}: {len(rows)} items, "
          f"{len({r['template_id'] for r in rows})} templates")
    print("  labels:", dict(Counter(r["label"] for r in rows)))
    print("  signal_types:", dict(Counter(r["signal_type"] for r in rows)))
    print("  ambiguous:", sum(1 for r in rows if r["ambiguous"]), "/", len(rows))


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--eval-fraction", type=float, default=0.75,
                         help="Fraction of TEMPLATES (not instances) assigned to eval.")
    parser.add_argument("--exemplars-out", type=Path,
                         default=DATASETS_DIR / "privacy_exemplars_v2.jsonl")
    parser.add_argument("--eval-out", type=Path,
                         default=DATASETS_DIR / "privacy_eval_v2.jsonl")
    args = parser.parse_args(argv)

    items = generate_all(args.seed)
    exemplar_items, eval_items = split_by_template(items, args.eval_fraction, args.seed)
    assert_no_leakage(exemplar_items, eval_items)

    write_jsonl(args.exemplars_out, exemplar_items)
    write_jsonl(args.eval_out, eval_items)

    print(f"Generated {len(items)} total items from {len(TEMPLATES)} templates.")
    _summary("EXEMPLAR BANK (train)", exemplar_items)
    _summary("EVAL SET (test)", eval_items)
    print(f"\nWrote {args.exemplars_out}")
    print(f"Wrote {args.eval_out}")
    print("\nZero template_id and exact-text leakage across the split (asserted).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
