# Task 1 report — Authoritative spike scene contract

## Status

DONE

The assigned repository is read-only in this agent's sandbox, so the complete
relative file set is staged under this directory for controller transfer.

## Files changed

- `spikes/__init__.py`
- `spikes/tour_quality/__init__.py`
- `spikes/tour_quality/scene_contract.py`
- `spikes/tour_quality/README.md`
- `tests/backend/test_tour_scene_contract.py`

## RED command/output summary

```sh
UV_CACHE_DIR=/private/tmp/hearthview-uv-cache \
PYTHONPATH=<staging-root>:<repo-root> \
uv run pytest -p no:cacheprovider <staging-root>/tests/backend/test_tour_scene_contract.py -q
```

Before implementation, the focused suite failed as expected: 21 failures, each
with `ImportError: cannot import name 'scene_contract' from
'spikes.tour_quality'`. The failure demonstrated the missing contract module,
not a test typo.

## GREEN command/output summary

The same focused command after implementation returned `21 passed in 0.09s`.

The mutation check additionally removed every named opening, collider, and
camera, removed the walkable polygon, and drifted the geometric island width
and envelope span by 4 mm. It returned actionable errors for `14/14` checks.

## Full-suite summary

```sh
HEARTHVIEW_DATA_DIR=<staging-root>/runtime-data \
UV_CACHE_DIR=/private/tmp/hearthview-uv-cache \
PYTHONPATH=<staging-root>:<repo-root> \
uv run pytest -p no:cacheprovider tests/backend \
  <staging-root>/tests/backend/test_tour_scene_contract.py -q
```

Result: `115 passed, 1 skipped, 5 warnings in 1.71s`.

The warnings are pre-existing execution-environment limitations: UV cannot
create its project environment lock and Hypothesis cannot write its database in
the read-only repository. The staged contract tests emit no warnings.

## Self-review

- Tests assert observable manifest and validation behavior with hand-derived
  literal meters; they do not inspect source text or mocks.
- The validator independently checks fixed meter literals and geometric
  relationships with a 0.003 m tolerance.
- Dataclasses are frozen and all repeated values use tuples; there are no
  mutable defaults.
- `to_manifest()` converts every tuple/dataclass into dict/list/string/number/
  boolean JSON primitives in contract-defined stable order.
- No unit-conversion code is duplicated: the required meter values are named
  literals because the printed-meter values are authoritative.
- Staged edits are confined to the required Task 1 paths plus the requested
  staging report. The README does not claim generated Blender artifacts exist.

## Concerns

- This agent could not write under
  `/Users/jackgarrigan/Developer/hello-world/codex-pdf-to-bim`; the controller
  must mechanically transfer the staged relative files before Task 2 consumes
  them.
- The wider suite required `HEARTHVIEW_DATA_DIR` to be redirected into staging
  because the repository's default `work/hearthview-data` location is read-only
  here.

## Fix round 1

### Status

DONE

### Coverage

`tests/backend/test_tour_scene_contract.py` now covers:

- an `envelope` of `None` and a wrong runtime type, asserting one actionable
  validation error rather than an exception;
- removal of each literal required opening, collision rectangle, and camera
  preset while its sibling metadata remains present;
- the literal room depth (`4.8514 m`), counter zone (`0.6604 m`), and island
  counter-face offsets (`1.7272 m`); and
- movement of either named counter rectangle face, asserting that its actual
  face invalidates the corresponding clearance; and
- drift beyond 3 mm for both new printed dimensions.

### RED command/output summary

```sh
UV_CACHE_DIR=/private/tmp/hearthview-uv-cache \
PYTHONPATH=<staging-root>:<repo-root> \
uv run pytest -p no:cacheprovider <staging-root>/tests/backend/test_tour_scene_contract.py -q
```

The regression tests first returned `6 failed, 31 passed`. They identified the
missing room-depth/counter-zone manifest values, the absent printed-dimension
validation, the `AttributeError` from dereferencing an invalid envelope, and
the incorrectly wall-measured clearances.

### GREEN command/output summary

The focused command returned `39 passed in 0.27s` after the contract added the
authoritative 4.8514 m room depth, derived 0.6604 m counter zone, actual
counter-face clearance checks, and the envelope guard.

### Full-suite command/output summary

```sh
HEARTHVIEW_DATA_DIR=<staging-root>/runtime-data \
UV_CACHE_DIR=/private/tmp/hearthview-uv-cache \
PYTHONPATH=<staging-root>:<repo-root> \
uv run pytest -p no:cacheprovider tests/backend \
  <staging-root>/tests/backend/test_tour_scene_contract.py -q
```

Result: `133 passed, 1 skipped, 5 warnings in 1.08s`.

The same sandbox-only UV lock and Hypothesis database warnings remain; no
contract-test warnings or failures occurred.
