# AI usage

I used Claude (Anthropic) as a pair-programmer for this problem.

## What it was used for

- Scaffolding the adapter/assembly split (`src/adapters/*` vs `src/app.py`)
  from a plain-English description of the desired separation.
- First draft of the retry/backoff logic in `benefits_register.py` and the
  page-walk/dedup logic in `resident_index.py`.
- First draft of `README.md` and this file's structure.
- Drafting the degradation-policy table in `DECISIONS.md` from a list of
  the failure cases I'd identified by hand.

## What it was not used for

- Deciding the degradation policy itself (which statuses exist, when a
  404 is returned vs a 200-with-status, when to retry vs not) — those
  calls were made first, in plain language, then implemented.
- The decision to require an explicit `benefit_ref` rather than attempt
  identity matching — made directly from the brief's explicit scoping of
  that as a stretch goal.
- Verifying behaviour — every claim in `README.md`'s floor checklist was
  checked by hand against the running services (including killing the
  XML service mid-session to confirm `/unified` degrades to `200` with
  an `unavailable` status instead of erroring), not taken on the model's
  word.

## How output was checked

- Ran `python3 -m unittest src.tests.test_floor -v` against the live mock
  services (not mocked-out fakes) after every change to an adapter.
- Manually killed `xml_service.py` mid-session and re-hit `/unified` to
  confirm the degraded-but-200 path actually happens, not just that the
  code looks like it should.
- Read every generated file fully before committing; nothing was taken
  as final on first generation.
