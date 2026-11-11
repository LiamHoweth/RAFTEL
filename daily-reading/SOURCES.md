# Sources to watch

Prioritize sources that answer a live RAFTEL question. The current emphasis is a stationary sorting arm, with mobile household manipulation as a later stage.

## Useful now

- **Hugging Face / LeRobot:** [documentation](https://huggingface.co/docs/lerobot/index) and [repository](https://github.com/huggingface/lerobot). Watch hardware interfaces, calibration, demonstration recording, dataset formats, policy evaluation, and release compatibility. The [SO-101 guide](https://huggingface.co/docs/lerobot/so101) is an example of an integrated arm workflow, not a hardware selection for RAFTEL.
- **Physical Intelligence:** [research and announcements](https://www.pi.website/blog). Watch how policies adapt to new hardware, how failures guide data collection, inference latency, and availability of code or models. Hosted services require separate evaluation of data handling, connectivity, cost, and access.
- **NVIDIA robotics:** [Isaac Lab](https://github.com/isaac-sim/IsaacLab) and [Isaac GR00T](https://github.com/NVIDIA/Isaac-GR00T). Watch manipulation benchmarks, simulation fidelity, model requirements, and demonstrated support for the selected arm. An announcement is not proof that RAFTEL's hardware is supported.

## Later-stage context

- **Figure:** [news and technical write-ups](https://www.figure.ai/news). Watch household manipulation, recovery, unseen-object evaluation, and whole-body coordination. Use evaluation design as inspiration; do not treat a proprietary humanoid demo as a drop-in capability.

## Expand from the repository

Once the hardware and stack are documented, add the exact manufacturers' manuals, upstream release/security feeds, relevant robotics papers, and comparable open-source builds. Track companies only when they offer a useful comparison for the current task. Prefer links to the specific announcement or experiment over general news summaries.

## Evaluate every story

Record publication/event dates separately when they differ, what changed, the evidence behind performance claims, and which RAFTEL file or decision makes it relevant. Check licensing, deployment requirements, and repeatability before recommending adoption.

Baseline checked: 2026-11-11 (UTC).
