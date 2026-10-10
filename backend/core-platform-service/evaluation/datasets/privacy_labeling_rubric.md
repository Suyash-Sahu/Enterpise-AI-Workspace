# Privacy Sensitivity Labeling Rubric — v1

Written before a single corpus item was generated, and applied unchanged
throughout generation. This is the codebook: a reviewer should be able to take
any item in the corpus, apply the rules below, and reproduce its label without
consulting the person who wrote it.

## Why a rubric at all

A classifier's benchmark is only as defensible as its ground truth. If the
labels come from one person's gut sense of "this sounds confidential," the
eval score measures agreement with that person's intuition, not with any
stated policy. This document is the policy. Every label in
`privacy_corpus_v2.jsonl` traces to a rule below, not to a judgment call made
in the moment of writing the item.

## The three labels

### `public`

Safe to leave the organization's control entirely — safe on a public website,
safe in a cloud LLM prompt, safe read by a stranger. An item is `public` only
if it meets ALL of:

1. Contains no named individual's personal data (name+identifier, name+role
   inside a sensitive context, health/financial/legal detail tied to a person).
2. Contains no regulated identifier (SSN, card/bank number, passport, national
   ID, private key, credential, connection string, API key).
3. Contains no information whose disclosure would give a competitor, attacker,
   or the general public something the organization has not chosen to publish
   (unreleased roadmap, unpatched vulnerability, pending legal matter, internal
   headcount/budget/performance figures).
4. Is either already public-facing in nature (documentation, published specs,
   general technical explanation, marketing copy) or is a general
   conceptual/how-something-works question with no organization-specific
   content at all.

### `internal`

Organizationally private but not independently regulated. Its disclosure is
an internal-policy violation, not (by itself) a legal, financial, or
safety incident. An item is `internal` if it meets criterion 1 or 2 below AND
fails no `confidential` criterion (see the tie-break rule):

1. Describes internal-only process, planning, or infrastructure detail
   (runbooks, architecture decisions, sprint/roadmap status, internal tooling,
   non-public internal network addressing) with no regulated identifier and no
   named individual's sensitive personal data.
2. Names an employee only in a role/directory sense (name + title + team),
   with no compensation, performance, health, or disciplinary content attached.

### `confidential`

Regulated, individually sensitive, or high-severity-if-disclosed. An item is
`confidential` if it meets ANY of:

1. Contains a regulated personal identifier: SSN, national ID (e.g. Aadhaar),
   passport number, payment card number, bank account/routing number, driver's
   license number, private cryptographic key, API key/credential,
   connection string with embedded secret.
2. Contains health information tied to an identifiable person (diagnosis,
   prescription, treatment, blood type, mental health).
3. Contains compensation, payroll, performance-rating, or disciplinary detail
   tied to a named individual.
4. Contains legally privileged material (attorney-client communication,
   active litigation strategy, merger/acquisition target or terms before
   public announcement).
5. Contains financial account detail, KYC data, or a customer's payment
   instrument.

## The signal-type axis (not a label — a generation-design tag)

Every generated item is also tagged with how its sensitivity signal is carried,
so the corpus deliberately spans easy and hard cases rather than only the easy
ones a keyword search would find:

- **`explicit_identifier`** — a regulated identifier is textually present
  (a card number, an SSN, a key block). The Week-1 rule-based detector layer
  is aimed squarely at this tag; a classifier that only handled this tag would
  still score well and still be badly incomplete.
- **`contextual`** — sensitivity comes from subject matter and framing, not a
  matched pattern (a payroll discussion with no visible SSN; an M&A memo with
  no named deal terms). This is what the embedding/LLM-judge stages exist for.
- **`surface_similar_benign`** — a deliberate hard negative: contains a
  pattern or vocabulary that resembles a sensitive signal but is not one (an
  order number that is not a card number; a "salary calculator" blog post that
  discusses salary in the abstract, attached to nobody; a security-training
  document that discusses phishing techniques). These exist to catch a
  classifier that over-fires on surface pattern-matching and to make
  precision, not just recall, a real number in this corpus.

## The ambiguity flag and its tie-break rule

Some generated items are deliberately constructed to carry mixed signals —
a genuinely public-sounding update that happens to include one incidental
internal detail; an internal process description that brushes against a
regulated subject without naming an individual. These get `ambiguous: true`
in their metadata. Ambiguity is a property of the ITEM's construction, decided
at template-design time, before any specific instance is generated — it is
not assigned after the fact by eyeballing a finished piece of text.

**Tie-break rule, applied mechanically, not by discretion:** when an item
plausibly satisfies criteria for two adjacent tiers, it is labeled at the MORE
sensitive of the two. This is a standard, independently-justified convention
in data-loss-prevention and PII-labeling practice — err toward the safer
classification when a human labeler would genuinely disagree — and is
**not** derived from this project's own router logic, even though it reaches
the same "escalate on uncertainty" shape. That resemblance is disclosed here
rather than left for a reviewer to notice: labeling the benchmark with the
same philosophy the system under test uses is a real limitation, not a
coincidence to hide. It means the ambiguous subset is easier for THIS
classifier's escalation posture than it might be for a classifier of a
different design, and the paper should say so when reporting the ambiguous
subset's accuracy separately from the rest.

## Independent second-rater protocol

Rubric labels (including tie-break-resolved ambiguous ones) are checked
against an independent rater: a separate LLM call, differently prompted
(no access to this rubric's exact wording, no access to
`app/privacy/classifier.py`, asked to reason from a plain-language description
of the three tiers rather than this document's rule list) so agreement is not
inflated by both raters reading the same instructions. Agreement is reported
as an explicit dataset-quality metric (`% agreement` and Cohen's kappa) in
`privacy_corpus_v2_rater_agreement.json`.

**Disagreements are not auto-resolved.** They are written to
`privacy_corpus_v2_disagreements.jsonl` for manual adjudication before the
corpus is treated as final ground truth for a paper. Until adjudicated, an
item on that list should not be cited as an example of settled ground truth.

## Provenance and PII statement

Every named person, company, email address, SSN, card number, address, and
account number in this corpus is generated by the `Faker` library
(`evaluation/datasets/generate_privacy_corpus.py`). None of it identifies a
real person or organization. Card numbers pass the Luhn checksum and SSNs
match the standard format specifically so the corpus exercises the same
validated detectors a real deployment would face, without ever containing
real regulated data. Any resemblance to an actual person, company, or account
is coincidental and a product of the generator's random sampling, not of
copying any real record.

## Versioning

- **v1 (this document):** first version, written 2026-09-12 before
  `generate_privacy_corpus.py` was run. Not amended after generation without a
  version bump and a note on what changed and why.
