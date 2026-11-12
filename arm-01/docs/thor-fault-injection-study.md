# Offline fault-injection pack

[`thor_fault_injection_study.py`](../tools/thor_fault_injection_study.py) adds a
deterministic, reusable fault pack using the existing `DiagnosticReplay`,
`MockArm` and `Sorter` contracts. It records executable fault-persistence and
held-object uncertainty witnesses. It changes no core implementation and adds
no transport, hardware backend or automatic recovery capability.

The useful gap was a reproducible **combined evidence pack**: existing unit
tests already check individual protocol/task faults, but did not expose two
observer-indistinguishable release failures with different fixture truth in a
single report. The new pack keeps those layers separate and never turns a mock
placement, acknowledgment or step count into physical success.

## Eleven bounded cases

The [revisioned configuration](../config/thor-fault-injection-v1.json) specifies
the exact eleven case identities, seed and a declared synthetic status-age bound.
Each case gets fresh logical state.

| Case | Executable witness |
| --- | --- |
| Stale status | A report older than the synthetic age bound faults |
| Partial status | A six-channel response fails the seven-channel contract |
| Out-of-order status | A previously older sequence fails after a newer one |
| Shoulder disagreement | Synthetic B/C channel angles disagree |
| Pending-command reset | An accepted but uncompleted command is invalidated |
| Lost acknowledgment and incremental retry | Retrying an unacknowledged increment doubles its modeled effect |
| Grasp acknowledgment lost after effect | The fixture holds an object, while task knowledge is unknown |
| Release acknowledgment lost before effect | The fixture still holds the object; task aborts with unknown state |
| Release acknowledgment lost after effect | The fixture has released/placed the object; the same observer trace still aborts with unknown state |
| Protocol reset during transfer | The diagnostic fixture resets and raises the existing `ArmFault`; logical stop preserves a held object |
| Ordinary false-grasp exhaustion | Existing `MockArm.failed_grasps` exhausts the configured retry budget, records failure and continues to account for the next object |

For each of the five protocol faults, the tool attempts a new command,
completion, another status request and a fresh apparently valid observation.
All must remain rejected. It then resets and tries again: reset may replace
the diagnostic fault **reason**, but it must not restore a ready state. The
accepted command must never acquire a false completion; its receipt is
invalidated and completed synthetic steps stay unchanged.

The lost-acknowledgment case is an explicit counterexample to blind retry.
One `G91 A1` followed by the same increment leaves the parser target at 2, even
though neither synthetic acknowledgment was received. Synthetic completion can
occur before an acknowledgment. The fixture's per-command acknowledgment flags
are privileged simulated truth; they are **not an attribution algorithm for
untagged real GRBL `ok` bytes**. This case does not claim that an acknowledgment
timeout automatically latches the existing replay; it demonstrates ambiguity.

The [source replay study](thor-controller-replay.md) defines the supported
arithmetic/protocol subset. The [GRBL warning audit](thor-grbl-source-warnings.md)
documents why that subset is not a demonstrated full firmware parser.

The ordinary false-grasp case is separate from `ArmFault` abort behavior. It
uses the existing mock's configured failure set, observes exactly the configured
number of attempts, records `object-00` as failed and successfully processes
`object-01` in the logical model. No failed grasp becomes a sorted object.
Tests exercise budgets 1, 2 and 5 rather than assuming the packaged default.

## Observer knowledge and fixture truth

A private subclass of `MockArm`, scoped only to this tool, raises injected
`ArmFault` exceptions before/after selected logical effects. `Sorter` handles
those exceptions through its existing abort/stop path. The subclass does not
become a packaged backend or rewrite the task state machine.

The two release-loss worlds use the same object inputs, public method calls,
exception message, sorter events, aborted result and rejected follow-up calls.
Their complete observer-visible trace hashes match. Their separately reported
**fixture oracle truth** differs:

| World | Fixture held object | Fixture placement ledger | Observer held-object knowledge |
| --- | --- | --- | --- |
| Loss before release effect | `object-00` | Empty | Unknown |
| Loss after release effect | None | `object-00` recorded | Unknown |

The after-effect oracle placement does not create a successful task result:
both worlds abort without any sorted object and leave `object-01` pending.
No placement verification occurs in either interrupted task. The case label
and oracle columns are deliberately excluded from observer inference.

`unknown_after_fault` is **pack-only bookkeeping**, not a new sensor/state
capability in core `MockArm`. The tool never clears it. It calls stop twice,
tries move/grasp/release/verification after stop, and reruns the sorter. These
operations must remain blocked/aborted without changing each world's held or
placement oracle state. A successful rerun or silently cleared uncertainty
would fail the pack. Logical stop does not demonstrate physical motor-energy
interruption or controlled gravity behavior.

## Reproduction and evidence

From the installed development environment in `arm-01`:

```powershell
python tools/thor_fault_injection_study.py
python tools/thor_fault_injection_study.py --output ../.work/controller/fault-injection-next.json
python -m pytest tests/test_thor_fault_injection_study.py
```

Output includes the eleven cases, actual exception records, per-case boolean
invariant checks, observer traces/hashes, separate oracle state, packaged
implementation fingerprints, seed/configuration, raw configuration hash and
producer-script hash. Fingerprints include the existing controller replay and
its source-conversion dependency. Repeated runs with the same inputs are
deterministic; changing the seed is explicit and keeps the ambiguity check.

The configuration is bounded to 64 KiB. Schema/revision/evidence class, integer
seed, finite positive synthetic age up to 60 seconds and the exact ordered
case identities are checked. Duplicate JSON keys, nonfinite values, unknown
fields, incomplete cases and transport-like configuration are rejected.
Existing output files are refused; generated reports use LF. No network,
native tooling, wall-clock delay, device access or external service is needed.

Exit 0 means the expected **fault invariants and counterexamples** were
observed, not that a fault-free robot or successful sort was demonstrated.
Exit 1 preserves a report containing failed invariants. Exit 2 indicates invalid
configuration/output. Thirty-five focused tests exercise the pack, indistinguishable
worlds, explicit unknown state, post-stop operations/rerun, malformed input,
provenance, deterministic output and output preservation.

This is logical simulation only. It does not implement full E3 commissioning,
real response parsing/transport, physical grasp sensing, contact/drop detection,
recovery, hardware stop validation or a sorting reliability result. Those remain
separate requirements with independent evidence gates.
