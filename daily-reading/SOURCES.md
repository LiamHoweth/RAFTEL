# Sources to watch

Prioritize the next decision in [nextSteps.md](../nextSteps.md). The current baseline is a stationary Thor-derived sorting arm; physical hardware, fabrication and actuator capacity remain unqualified.

## Useful now

- **Thor mechanics and source model:** [pinned native CAD](https://github.com/AngelLM/Thor/tree/286b081fe6f056d87c379b884781ef77ff6a0159) and [pinned ROS controller](https://github.com/AngelLM/Thor-ROS/blob/e11a56b5aa0d89f0b68a3ea7bd084eab4a050952/ws_thor/src/thor_controller/src/thor_interface.cpp). Follow actual part membership, wrist coupling, belt paths and datum frames. Read our [geometry](../arm-01/docs/thor-geometry.md) and [transmission](../arm-01/docs/thor-transmission-study.md) evidence first; a controller convention is not physical calibration.
- **Statics and dynamics:** [Modern Robotics 5.2](https://modernrobotics.northwestern.edu/nu-gm-book-resource/5-2-statics-of-open-chains/), an undated primary teaching resource. Use it to understand joint-load calculations before comparing actuator specifications.
- **Exact actuator data:** [StepperOnline 17HS13-0404S-PG5](https://www.omc-stepperonline.com/nema-17-stepper-motor-bipolar-l-33mm-w-gear-ratio-5-1-planetary-gearbox-17hs13-0404s-pg5) and the other upstream-linked models in [our load study](../arm-01/docs/thor-load-analysis.md). Track drawings, masses, torque-speed test conditions and gearbox limits; keep supplier claims distinct from measured performance.
- **Printer and slicer:** [Anycubic Kobra 3 Max specifications](https://us.anycubic3d.com/products/kobra-3-max), [official manual](https://wiki.anycubic.com/k3-max/anycubic_kobra_3_max_combo_user_manual-en-v1.1_compressed.pdf), and [our fabrication record](../arm-01/hardware/fabrication.md). Track exact profile/nozzle, usable print area, part orientation and sliced mass. Do not infer the user's installed configuration from stock specifications.
- **Filament-specific technical sheets:** [Prusament PLA v1.1](https://prusament.com/wp-content/uploads/2022/10/PLA_Prusament_TDS_2021_10_EN.pdf), [PETG v1.1](https://prusament.com/wp-content/uploads/2022/10/PETG_Prusament_TDS_2021_10_EN.pdf), and the exact ABS edition referenced in [our material study](../arm-01/docs/thor-load-analysis.md). Substitute the actual filament vendor's data when known. Watch print direction, stiffness, creep, thermal test conditions and density—not family labels alone.
- **FreeCAD and workbench compatibility:** use the pinned sources in [our compatibility record](../arm-01/docs/thor-dependency-compatibility.md). Watch schema/kernel changes affecting saved models; latest-version imports do not prove legacy feature rebuilds.

## Later-stage learning and simulation

- **Hugging Face / LeRobot:** [documentation](https://huggingface.co/docs/lerobot/index), [repository](https://github.com/huggingface/lerobot), and the [November 5 v0.7.0 release](https://huggingface.co/blog/lerobot/lerobot-release-v070). Prioritize recording, calibration, evaluation and verified selected-hardware support when those gates are reached. Stock SO-101 is a reference, not the chosen six-axis baseline.
- **NVIDIA robotics:** [November 9 CoRL announcement](https://blogs.nvidia.com/blog/robotics-simulation-advancements-corl/), [Isaac Lab](https://github.com/isaac-sim/IsaacLab) and [GR00T](https://github.com/NVIDIA/Isaac-GR00T). Require a traceable model and deployment/support checks before recommending adoption. Keep vendor demonstrations separate from repeatable RAFTEL results.

## Evaluation and recent research

- **PRISM / University of Michigan:** [November 10 CoRL coverage](https://news.engin.umich.edu/2026/11/prism-a-neural-network-component-for-better-robotic-motor-control/), [paper history](https://arxiv.org/abs/2607.23473) and [author protocols/results](https://lsh3163.github.io/prism/). Watch explicit success definitions, denominators, shared recovery states and physical-versus-simulated evidence. The paper was submitted July 26 and revised October 16; November coverage is not a new paper release. Policy adoption belongs after the current mechanical/sensing gates.
- **Google DeepMind robotics:** [Gemini Robotics 2.5 announcement, November 10](https://deepmind.google/blog/gemini-robotics-2-5-accelerates-real-world-physical-intelligence/). Kitting is a relevant task comparison; require trial denominators, actual access/hardware support and comparable conditions before drawing performance conclusions. Company-reported demonstrations do not validate ARM-01.

- **NTT physical AI:** [November 11 candidate-action world-model announcement](https://group.ntt/en/newsrelease/2026/11/11/261111b.html). Watch predicted-versus-observed outcomes and explicit task conditions. Small-robot shelf-loading results are company-reported; planned airport trials and a ready-to-integrate Thor implementation are not established by the release.

- **Cerulion replay:** [November 12 v2.0.0 release](https://github.com/cerulion-inc/cerulion/releases/tag/v2.0.0) and [versioned ROS replay contract](https://github.com/cerulion-inc/cerulion/blob/v2.0.0/docs/ros2_replay.md). Compare consumed-input preservation, explicit refusal and output-divergence reporting. Replay can publish live outputs; it is not inherently isolated from hardware. This is architecture reading, not an ARM-01 adoption decision.
- **MERL manipulation evaluation:** [TacSushi, TR2026-173, November 13](https://www.merl.com/publications/docs/TR2026-173.pdf). Watch trial denominators, held-out conditions and evaluator uncertainty. Its visual-quality success rule and food-handling embodiment do not transfer directly to BenchSort.

- **ASUS Gallop:** [November 13 workstation-development post](https://press.asus.com/blog/factory-proven-physical-ai-asus-gallop-humanoid-robot). Watch whole-job acceptance criteria and fixed subsystem interfaces. Its 99.5%/20-second figure is a target, not a measured reliability result; factory setting and humanoid branding do not establish household suitability.

- **NVIDIA SimReady task walkthrough:** [November 13 pick-and-place tutorial](https://huggingface.co/blog/nvidia/simready-assets-robot-pick-and-place), verified November 17. Compare asset-profile checks with assembled-scene and whole-task evidence. This is later-stage reference reading, not an ARM-01 stack or hardware selection.

- **Genesis AI / Eno:** [November 17 funding and systems-strategy release](https://www.prnewswire.com/news-releases/genesis-ai-raises-500m-series-a-at-3-5b-valuation-to-master-human-level-dexterity-in-general-purpose-robots-and-deploy-at-scale-302941249.html), verified November 18. Watch the demonstration-to-deployment feedback loop and industrial-first scope. Funding, human-level capability language and deployment plans are company statements, not comparable household reliability measurements.

## Editorial checks

Record publication/event dates separately from verification dates. Identify whether a source is news, a living reference, a pinned code revision or older background. Link each item to an actual project decision. Check licensing, requirements and repeatability before adoption; publish fewer items when no relevant news changes the next action.

Watchlist updated: November 18, 2026. Genesis's November 17 announcement was verified today; NVIDIA's November 13 tutorial was verified November 17; ASUS's November 13 post was verified November 15; Cerulion release/documentation and the TacSushi report were verified November 14; NTT was verified November 13, and PRISM/Gemini Robotics 2.5 on November 12. Earlier reference entries retain their previous verification scope. Some manufacturer pages are undated living references. Access failures are limits on verification, not proof that a product or document is unavailable.
