# Detector Coverage Audit Design

Status: `DESIGNED_ONLY`. No missed-detection runtime rule or CVAT Issue is added in this milestone.

## Confirmed need

The visual audit of CVAT task 44/job 61 found clearly visible vehicles without boxes: the blue/white bus through CVAT frames 19–39, a green bus through most of frames 28–39, and a red minibus from approximately frame 29. The current Analyzer consumes tracked MOT boxes. An object that never becomes a track leaves no evidence in that input, so a tracker-only rule cannot detect this failure.

The runtime already preserves the required starting signals before tracking. Each `predictions/chunks/chunk_*.json` checkpoint contains normalized `detections` and `tracks`. Every detection has `frame_id`, `bbox`, `confidence`, `class_id`, and `class_name`; replay reads those detections back and verifies the chunk hash and regenerated tracks. This behavior is implemented in `tools/tracking_runtime.py` and mock-tested by the chunk/resume tests in `tests/test_scalable_pipeline.py`.

## Proposed read-only audit input

The first coverage-audit prototype should read locked chunk checkpoints plus MOT tracks. It must verify the checkpoint manifest and hashes before producing candidates. For each canonical class it may derive:

- detector boxes that were not represented by any tracker output in the same frame;
- short detector histories before or after an established track;
- confidence, center, size, and class history across nearby frames;
- nearby track motion extrapolated only across a short bounded interval.

The output label must be `POSSIBLE_MISSED_DETECTION`. A candidate is a request for visual review, not proof that an object exists and not permission to create a box.

## Candidate heuristic for later evaluation

A conservative candidate is a **bracketed detector-to-track coverage gap**:

1. detections of the same canonical class form a motion-consistent short history before and after a gap;
2. no compatible track box covers that history during the gap;
3. the detector evidence persists for more than one frame and exceeds a configured confidence floor;
4. the gap is short and the predicted center/size corridor remains plausible;
5. boundary entry/exit and strong overlap with another compatible tracked object lower confidence or suppress the candidate.

Candidate evidence would include the frame interval, canonical class, detector confidences, nearest track IDs, overlap values, and the exact thresholds used.

## Why it is not implemented now

Task 44 does not provide sufficient evidence to validate this heuristic. The blue/white bus has no useful detector continuation after its last tracked interval, the green bus has only one late tracked box, and the red minibus has no confirmed tracked identity. A bracketed-history heuristic would therefore miss the principal confirmed cases. Relaxing it to infer objects from track disappearance alone would invent a tracker-only false-negative rule and would confuse exit, occlusion, blur, and detector failure.

Before implementation, collect visually adjudicated sequences containing both true detector dropouts and hard negatives such as exits, full occlusions, parked objects, overlapping vehicles, and low-confidence clutter. Measure candidate precision and recall without changing boxes. Completely unseen objects will still require an independent detector/semantic signal and remain outside this design.

## Safety contract

- Read-only over locked detector and tracker artifacts.
- No CVAT annotation creation, deletion, relabeling, or automatic correction.
- No claim of `MISSED_DETECTION`; only `POSSIBLE_MISSED_DETECTION` after visual review.
- No reuse of ground truth at runtime.
- No candidate implementation until evidence supports thresholds and hard-negative behavior.
