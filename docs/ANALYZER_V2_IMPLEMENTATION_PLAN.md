# Analyzer v2 implementation plan

Written before implementation. Read v2 design, both external reports/comparison, v1 analyzer, stored flags and tracker exporter. New user requirement overrides the old plan's singleton exception: require at least two consecutive supporting frames. P26/P140 exists together only at frame99; intentionally cannot pass this requirement. No per-sequence tuning.

Files to create (existing runtime and validation files remain unchanged):

| File | Why / input → output |
|---|---|
| configs/review_v2.json | Separate experimental duplicate/event settings; never modifies v1 thresholds |
| tools/review_tracks_v2.py | Reuse v1 parser/analyze; MOT + v1 config + v2 config → schema2 raw flags and events. --compat-v1 delegates unchanged writer |
| tests/test_review_tracks_v2.py | Temporal positives/negatives, grouping, compatibility, no-reference runtime, config/output guards |
| tools/regress_analyzer_v2.py | Four stored MOT inputs → isolated v1/v2 outputs, byte-compat checks, counts and preservation hashes. No tracker run |
| docs/ANALYZER_V2_RESULTS.md | Regression, migration/commands, acceptance limits and reviewed new candidates |
| docs/ANALYZER_V2_FUTURE_SIGNALS.md | Missing-object/identity observability limitations from actual exporter |
| outputs/analyzer_v2_regression/ | New outputs, logs, evidence and comparison only; never old validation paths |

Algorithm frozen before regression: unordered simultaneous pairs, IoU>=0.75, center distance/minimum box diagonal<=0.10, symmetric width/height ratio<=1.35, all in at least2 consecutive frames. One flag per maximal qualifying run, anchored at second frame (confirmation), observed aggregate geometry and duration retained. Missing/interrupted overlap resets the run. These conservative engineering defaults are experimental, not calibrated. Crossing/nearby objects may still satisfy them; tests and visual adjudication determine acceptance, not a forced positive count.

Event grouping: only exact track + start/end + related identity set. Gap/reappeared on the same interval merge; unrelated or overlapping intervals do not. Preserve raw flags and stable IDs. Context padding2; optional total frame count is image metadata, not GT. Compatibility uses untouched schema1 writer; v2 JSON schema2 and separate v2 filenames avoid silently changing v1 CSV cells.

Acceptance: all25 baseline tests plus new tests; exact v1 CSV/JSON compatibility; inspect all new duplicate candidates; no invented GT-only runtime logic. Known singleton miss is documented. Small regression sample cannot satisfy the design's independent20-event precision gate; feature stays experimental unless justified by evidence. No automatic next phase.
