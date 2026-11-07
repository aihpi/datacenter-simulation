.PHONY: help setup data examples synth test eval eval-vertex demo smoke frontend-build clean

help:
	@echo "datacenter-simulation — make targets:"
	@echo "  make setup          install python deps (uv) and frontend deps (npm)"
	@echo "  make data           regenerate the seeded synthetic dataset + fixtures"
	@echo "  make examples       regenerate the themed example CSV bundles (data/examples/)"
	@echo "  make synth          write the datacenter-spec presets as CSVs (data/synthetisch/)"
	@echo "  make test           run the python unit/integration test suite (pytest)"
	@echo "  make eval           run the pipeline eval with the mock backend (Gate 2/3)"
	@echo "  make eval-vertex    run the pipeline eval with the vertex backend"
	@echo "  make demo           launch backend + frontend dev server (./run.sh)"
	@echo "  make smoke          launch live stack + Playwright smoke (./run.sh --smoke)"
	@echo "  make clean          remove caches and frontend build artifacts"

setup:
	uv sync
	cd frontend && npm install

data:
	PYTHONPATH=. uv run python data/generate.py

examples:
	PYTHONPATH=. uv run python data/generate_examples.py

synth:
	PYTHONPATH=. uv run python data/generate_synthetic_rz.py

test:
	uv run pytest -q

eval:
	LLM_BACKEND=mock uv run python eval/run_eval.py

eval-vertex:
	LLM_BACKEND=vertex uv run python eval/run_eval.py

frontend-build:
	cd frontend && npm run build

demo:
	./run.sh

smoke:
	./run.sh --smoke

clean:
	rm -rf .pytest_cache .run frontend/dist frontend/test-results frontend/playwright-report
	find . -path ./.venv -prune -o -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
