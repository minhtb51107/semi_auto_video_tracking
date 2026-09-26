# Analyzer v2 — future signals, not implemented

Runtime v2 reads only MOT predictions and two configs. No GT, reference association, evaluator, DontCare labels, image pixels or appearance embeddings enter detection. Ground truth is used only in the separate historical/offline adjudication of regression results.

## Missed coverage

Evidence: G10/0001 wholly missed; G12/0000 has severe coverage failure. MOT containing no stable prediction for an object cannot reliably establish that object's existence. **NOT_RUNTIME_DETECTABLE_WITH_CURRENT_SIGNALS** for a reliable never-detected-object rule. Do not replace this with `if GT and no prediction` or infer a missing car merely because nearby cars exist.

Actual exporter `tools/run_tracker.py`, `track_clip`: calls `model.track(persist=True)` and serializes returned `boxes.xyxy`, `boxes.id`, `boxes.conf`; skips frames with no assigned boxes.id. `write_mot` stores frame, ID, XYWH, confidence and placeholder fields. It does not retain pre-association detector candidates, matched/unmatched detection status, dropped detections, predicted Kalman state, lifecycle reasons or detector class. A short MOT track is observable, but why it is short is not.

Potential future instrumentation (not added): detector-before-tracker boxes with class/confidence, frame provenance and detector settings; association outcome and reason for dropped/unmatched candidates; temporal histories of unassigned detections. Persistent detector support without an assigned track could justify a **candidate coverage warning**, still confounded by false detector positives, occlusion, class filtering and entry/exit. It would not find a car that the detector also never saw. Require fresh validation and storage/privacy review appropriate to the actual deployment before expanding scope.

## Identity and localization

P54/0001 is an uncertain association conflict removed from eligible Car evaluation by ignore policy. P187/P229/0000 visibly reuse identity across sides of the street but are already flagged as gaps. P331/0000 remains uncertain between overlapping parked-car boxes. Internal G5 switch and two G1 Van splits in0000 remain missed.

MOT geometry cannot distinguish two very similar nearby cars from one duplicated object in all cases. It also cannot reliably separate physical identity changes from amodal/visible-box convention changes, ego-motion or occlusion. `possible_identity_merge` is therefore **not implemented**. GT ownership transitions are evaluation evidence, not available runtime features.

Possible future signals include per-detection history, camera/ego-motion estimates, lifecycle/association costs and independently evaluated appearance embeddings. These require a new scope and experiments; no ReID, model, training or exporter modification is included now. Stable but inaccurate localization and semantic ghosts likewise may have smooth geometry; existing flags cannot certify their absence.

## Human review boundary

Keep explicit residual coverage review and allow uncertainty labels. Do not auto-correct, merge IDs, remove duplicate boxes or skip all unflagged video based on v2. Obtain independent adjudication, hard overlapping-car negatives and a fresh held-out sequence before accepting precision/recall or moving to operational CVAT integration. No next phase is started here.
