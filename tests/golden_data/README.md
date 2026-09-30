# Golden QA regression manifest

`manifest.json` is a small permanent behavior-regression set. Rows marked
`SYNTHETIC_RULE_FIXTURE` are deliberately constructed geometry used to lock
deterministic Analyzer behavior; they are **not ground truth** and do not claim
to represent real-world error prevalence.

Rows marked `OBSERVED_REFERENCE_ONLY` point to existing validation evidence.
They are not copied or relabeled as ground truth and are not automatically
scored. Large images, datasets, model weights, and CVAT workspaces do not belong
in this directory.

`OBSERVED_RULE_FIXTURE` rows contain only lightweight geometry copied from a
locked, visually audited artifact. They lock confirmed rule behavior while the
linked report remains the source for the physical-object interpretation. They
are regression evidence, not a benchmark or synthetic ground truth.

Run:

```powershell
.venv\Scripts\python.exe -X utf8 tools/run_golden_qa.py
```

The runner checks the synthetic rule contracts and verifies that every required
case category has either an executable fixture or a documented observed
reference.
