# Run from the repository root. Local native paths never belong in source control.
.DEFAULT_GOAL := help
-include .raftel-local.mk
PYTHON := $(CURDIR)/arm-01/.venv/bin/python
BIN := $(CURDIR)/arm-01/.venv/bin

.PHONY: help setup verify demo benchmark analysis native-audit
help:
	@echo 'make setup         Install the pinned Python development environment'
	@echo 'make verify        Run tests, lint, CLI studies and offline wheel checks'
	@echo 'make demo          Sort ten synthetic objects with the mock backend'
	@echo 'make benchmark     Evaluate ten seeded logical layouts'
	@echo 'make analysis      Run assumed-load and nominal kinematics studies'
	@echo 'make native-audit  Audit the configured compatible CAD copy (no saving)'

setup:
	python3 -m venv arm-01/.venv
	"$(PYTHON)" -m pip install -r arm-01/requirements-dev.lock -e 'arm-01[dev]'

verify:
	/bin/sh scripts/verify.sh

demo:
	"$(BIN)/raftel-sort" --seed 42 --count 10

benchmark:
	"$(BIN)/raftel-evaluate" benchmark --seed 42 --layouts 10

analysis:
	cd arm-01 && "$(PYTHON)" tools/engineering_analysis.py
	cd arm-01 && "$(PYTHON)" tools/thor_kinematics.py

# The existing runner isolates preferences and preserves every run's evidence.
native-audit:
	@test -n "$(FREECAD)" -a -n "$(THOR_ASSEMBLY)" -a -n "$(FASTENERS)" -a -n "$(GEARS)" || { echo 'Configure native paths in .raftel-local.mk; see docs/mac-setup.md'; exit 2; }
	@mkdir -p .work/native
	@lock="$(CURDIR)/.work/native/.audit-lock"; \
	mkdir "$$lock" 2>/dev/null || { echo 'Another native audit holds the lock; inspect active runs before removing a stale lock.'; exit 2; }; \
	trap 'rmdir "$$lock"' EXIT HUP INT TERM; \
	"$(PYTHON)" -c 'import shutil, sys; sys.exit(0 if shutil.disk_usage(".").free >= 50 * 1024**3 else "Native audit requires at least 50 GiB free.")' && \
	run=$$(mktemp -d "$(CURDIR)/.work/native/audit-XXXXXX") && \
	cd arm-01 && "$(PYTHON)" tools/run_freecad_audit.py \
	  --freecad "$(FREECAD)" --source "$(THOR_ASSEMBLY)" \
	  --module-path "$(FASTENERS)" --module-path "$(GEARS)" \
	  --report "$$run/assembly.json" --recompute changed --shape-scope none --timeout 480
