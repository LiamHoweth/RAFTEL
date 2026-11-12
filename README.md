# RAFTEL

RAFTEL is developing affordable, modular robots that can perform useful household chores and assist people. The long-term goal is an accessible general-purpose household robot; the current project is a stationary manipulation testbed.

## ARM-01 — BenchSort

[ARM-01](arm-01/README.md) targets an articulated arm with **six independent arm joints and one motorized parallel gripper**. Liam has allowed **up to eight actuators** and directed the team to **study Thor first** as the existing editable CAD baseline: seven arm motors (including a coupled shoulder drive) for six arm axes, plus one gripper motor. This supersedes the initial seven-total-actuator target. It is a study direction, not a fabrication or purchase approval. The proposed demonstration is to identify and sort ten lightweight objects, placed at variable positions, into three boxes on a workstation.

The repository includes a runnable **logical sorting simulation** and separate offline engineering studies, including nominal spatial kinematics, bounded local IK, conditional loads and print-draft preparation. Final CAD, actuator sizing, camera perception, calibrated robot kinematics, collision-aware physical trajectories and physical validation remain engineering milestones. Design targets and research references are not verified performance specifications.

The Thor compatibility assembly restores and recalculates with pinned addons and an exact static Art1 snapshot. The [corrected geometry inventory](arm-01/docs/thor-geometry-completeness.md) contains **518 installed solid leaves**, including two wrist belts omitted from the historical 516-leaf inventory. Source joint-axis checks and conditional mass/load scenarios are reproducible; the original Art1 feature history and physical qualification remain separate gates. The [evidence index](arm-01/docs/desktop-evidence-index.md) maps current studies to their bounded checks and unresolved inputs.

Start with [nextSteps.md](nextSteps.md) for current evidence, blockers, and the next three actions for Liam and Codex. Future agents must follow [AGENTS.md](AGENTS.md).

## Run the software

Requires Python 3.11 or newer. No robot, camera, ROS installation, or GPU is needed.

```sh
cd arm-01
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.lock -e '.[dev]'
raftel-sort --seed 42
python -m pytest
ruff check .
ruff format --check .
python tools/engineering_analysis.py
```

See the [ARM-01 setup guide](arm-01/README.md) for Windows activation, configuration, failure scenarios, and evidence limits. Installing dependencies needs package-index access; the installed mock demonstration runs offline.

## Engineering navigation

| Topic | Document |
| --- | --- |
| Mission and design principles | [Vision](docs/vision.md) |
| Phased development and acceptance gates | [Roadmap](docs/roadmap.md) |
| Proposed requirements | [Requirements](arm-01/docs/requirements.md) |
| Software boundaries and current implementation | [Architecture](arm-01/docs/architecture.md) |
| Desktop implementation results and next gates | [Run record](docs/arm01-desktop-run-2026-11-11.md), [evidence index](arm-01/docs/desktop-evidence-index.md) |
| Existing mechanical references | [Research](arm-01/docs/research.md) |
| Reusing proven CAD | [CAD reuse plan](arm-01/docs/cad-reuse.md) |
| Mechanical selection rationale | [Mechanical ADR](docs/architecture-decisions/0001-mechanical-starting-point.md) |
| Compatible Thor assembly | [Compatibility baseline](arm-01/docs/thor-assembly-compatibility.md) |
| Thor geometry and frames | [Geometry study](arm-01/docs/thor-geometry.md) |
| Thor mass and static loads | [Load study](arm-01/docs/thor-load-analysis.md) |
| Thor transmissions | [Transmission study](arm-01/docs/thor-transmission-study.md) |
| Thor joint/motor coordinates | [Joint map](arm-01/docs/thor-joint-map.md) |
| Thor native CAD evidence | [Native validation](arm-01/docs/thor-native-validation.md) |
| Thor cost evidence | [Cost study](arm-01/hardware/thor-cost-study.md) |
| Load estimates | [Mechanical analysis](arm-01/docs/mechanical-analysis.md) |
| Parts and purchasing status | [Candidate BOM](arm-01/hardware/bom.md) |
| Workstation and safety | [Workstation](arm-01/docs/workstation.md), [Safety](arm-01/docs/safety.md) |
| Future detachable/mobile interface | [Mobile integration](arm-01/docs/mobile-integration.md) |
| Test methods and evidence categories | [Verification plan](arm-01/docs/verification-plan.md) |

## Contribution and licensing

Preserve existing work, use feature branches, and keep implementation and handoff documentation together. Every physical design change needs explicit assumptions, relevant calculations, and validation appropriate to its risk. No purchases or hardware motion are authorized by the mock software.

RAFTEL's own distribution license has not been selected. Do not assume that public source availability grants reuse rights. Upstream mechanical, firmware, and software licenses must be checked separately before importing or distributing any assets or derivatives.
