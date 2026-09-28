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
  -> CVAT Issue adapter (human comment + structured audit metadata)
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

## Future gates

Semantic verification, detector-level missed-object proposals, generic model taxonomy mapping, BoT-SORT exposure, live 1,000+ frame benchmarks and concurrent workers are not implemented. Analyzer v2 inter-track heuristics remain class-agnostic and need held-out evidence before a class-aware behavior change.
