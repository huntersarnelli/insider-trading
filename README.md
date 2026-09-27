# Insider Purchase Signal

An event study testing whether opportunistic open-market insider purchases (SEC Form 4, code P)
beat randomly timed purchases of the same stocks over 20–60 trading days. See `project.md` for the plan.

**Setup:** `pip install -r requirements.txt`

**Run Phase 1 (data pipeline):** open `notebooks/01_data_pipeline.ipynb` and run all cells.
Outputs go to `data/processed/` and `results/` (neither is committed; regenerate them locally).

**Run Phase 2 (event study):** open `notebooks/02_event_study.ipynb`, or run `python run_study.py`.
Outputs go to `results/phase2_event_study/`. Tests: `python -m pytest tests`.

Functions live in `src/`; notebooks only call them. Research and educational use only. Not investment advice.
