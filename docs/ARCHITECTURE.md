# Configurable CVAT Tracking Architecture

```text
CVAT task/job
  -> Frame Source (validated CVAT frames)
  -> Detector protocol
       UltralyticsYOLODetector
  -> Detection(frame, bbox, confidence, class_id, class_name)
  -> Tracker protocol
       ByteTrackTracker
  -> TrackBox(frame, track_id, bbox, confidence, class_id, class_name)
  -> class-aware MOT/internal artifacts + chunk checkpoints
  -> CVAT annotation adapter (detector class -> configured CVAT label ID)
  -> Analyzer v2
  -> review event aggregation
  -> deterministic priority + optional selection
  -> non-flagged random QA plan
  -> CVAT Issue adapter (human comment + structured audit metadata)
  -> human correction/resolution
  -> read-only final validation
  -> release readiness decision
```

## Runtime boundaries

`tools/tracking_runtime.py` owns normalized inference contracts. Ultralytics `Results` and `Boxes` never leave `UltralyticsYOLODetector`. `ByteTrackTracker` receives normalized detections and returns normalized tracks. The CVAT runner can substitute mocks without changing orchestration.

`configs/label_mappings.json` maps detector class IDs to canonical labels and CVAT aliases. `tools/label_mapping.py` validates overlaps and builds a class→concrete CVAT label-ID plan from the task. Class identity is stored in MOT column 8 and read back before annotation creation.

ByteTrack uses one temporal association state, matching the existing Ultralytics workflow. The adapter namespaces `(returned class, native track ID)` into a global external track ID, so any class change cannot silently become one cross-label CVAT track.

## Chunk/resume model

Frame download checkpoints every image. Inference checkpoints normalized detections/tracks after each chunk. ByteTrack internal state is intentionally not pickled because it is library/version-specific. Resume creates a fresh tracker and deterministically replays cached detections; replayed TrackBox output must equal the locked chunk output. Only uncompleted frames call the detector.

A changed model/config/label mapping/chunk size/frame inventory, a corrupt checkpoint, or nondeterministic replay safe-fails.

## Safety boundary

Annotation writes remain append-only. Remote track signatures are reconciled before retry, Issue identity uses deterministic event markers, and remote annotation hashes guard post-human-edit reruns. Task-level orchestration never shares workspaces between jobs and records partial failures without discarding completed job results.

Final validation and release-check are separate read-only stages. They fetch the live CVAT annotation and Issue state, compare the annotation hash before and after validation, then write compact workspace JSON. Release-check never exports or edits annotations.

## QA boundary

`review_priority.py` adds deterministic severity, score and machine-readable explanations after event aggregation. It never changes raw flags, Analyzer reasons or event IDs. Default selection includes every event for backward compatibility.

`qa_workflow.py` deterministically samples frames outside all flagged context ranges using task/job, annotation hash, seed and config. QA samples use a distinct Issue namespace. CVAT remains the source of truth for Issue resolution.

Inter-track Analyzer comparisons use canonical/CVAT-label compatibility from the locked label plan when both detector classes are mapped. For example, COCO car, bus, and truck remain eligible as the same canonical `vehicle`. With no complete mapping, known subclasses retain the prior exact-class check; missing class identity follows legacy geometry-only behavior so older MOT files remain usable.

## Future gates

Semantic verification, detector-level missed-object proposals, automatic relabeling, generic model taxonomy mapping, BoT-SORT exposure, live 1,000+ frame benchmarks and concurrent workers are not implemented. Pre-tracker class/confidence histories are preserved in chunk checkpoints; `DETECTOR_COVERAGE_AUDIT_DESIGN.md` explains why current evidence supports a design only, not a runtime missed-object rule. Release readiness does not prove semantic correctness.
