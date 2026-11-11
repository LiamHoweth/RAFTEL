# RAFTEL

RAFTEL is developing affordable, modular robots that can perform useful household chores and assist people. The long-term goal is an accessible general-purpose household robot; the current project is a stationary manipulation testbed.

## ARM-01 — BenchSort

[ARM-01](arm-01/README.md) targets an articulated arm with **six independent arm joints and one motorized parallel gripper**. Liam has allowed **up to eight actuators** and directed the team to **study Thor first** as the existing editable CAD baseline: seven arm motors (including a coupled shoulder drive) for six arm axes, plus one gripper motor. This supersedes the initial seven-total-actuator target. It is a study direction, not a fabrication or purchase approval. The proposed demonstration is to identify and sort ten lightweight objects, placed at variable positions, into three boxes on a workstation.

The repository begins with a runnable **logical sorting simulation**, engineering research, and preliminary calculations. This is not a physical robot demonstration. Final CAD, actuator sizing, camera perception, inverse kinematics, collision-aware trajectories, and physical validation remain engineering milestones. Design targets and research references are not verified performance specifications.

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
| Existing mechanical references | [Research](arm-01/docs/research.md) |
| Reusing proven CAD | [CAD reuse plan](arm-01/docs/cad-reuse.md) |
| Mechanical selection rationale | [Mechanical ADR](docs/architecture-decisions/0001-mechanical-starting-point.md) |
| Load estimates | [Mechanical analysis](arm-01/docs/mechanical-analysis.md) |
| Parts and purchasing status | [Candidate BOM](arm-01/hardware/bom.md) |
| Workstation and safety | [Workstation](arm-01/docs/workstation.md), [Safety](arm-01/docs/safety.md) |
| Future detachable/mobile interface | [Mobile integration](arm-01/docs/mobile-integration.md) |
| Test methods and evidence categories | [Verification plan](arm-01/docs/verification-plan.md) |

## Contribution and licensing

Preserve existing work, use feature branches, and keep implementation and handoff documentation together. Every physical design change needs explicit assumptions, relevant calculations, and validation appropriate to its risk. No purchases or hardware motion are authorized by the mock software.

RAFTEL's own distribution license has not been selected. Do not assume that public source availability grants reuse rights. Upstream mechanical, firmware, and software licenses must be checked separately before importing or distributing any assets or derivatives.
