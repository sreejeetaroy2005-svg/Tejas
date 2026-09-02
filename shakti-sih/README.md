# Tejas — AI-Enabled Well-to-Surface Digital Twin (SIH Prototype)

Decision-support digital twin for a heavy-oil well (BGW-01) that coordinates
Cyclic Steam Stimulation (CSS) and Sucker Rod Pump (SRP) operations.

**This is a demonstration prototype using synthetic data.** It is not connected
to real Oil India field systems and does not perform autonomous control —
all recommendations require operator review.

## Project structure

```
tejas-sih/
  backend/          FastAPI app, ML/rules engine, synthetic data
    app/
      main.py        FastAPI entrypoint
      schemas.py      Pydantic response/request models
      services/       risk engine, optimizer, viscosity model, data loading
      routers/        API route definitions
    data/             generated CSV lives here (bgw_01_daily.csv)
    scripts/          synthetic_data_generator.py
    tests/            unit tests for risk engine / optimizer
  frontend/          Next.js dashboard (built in a later phase)
  docs/
    assumptions.md    all modeling assumptions, documented as we build
```

## Status

- [x] Phase 0 — Repo scaffold
- [x] Phase 1 — Synthetic data generator
- [ ] Phase 2 — FastAPI backend + real data
- [ ] Phase 3 — Risk engine
- [ ] Phase 4 — Recommendation + simulator logic
- [ ] Phase 5 — Frontend scaffold
- [ ] Phase 6 — Dashboard build-out
- [ ] Phase 7 — Polish + explainability
- [ ] Phase 8 — Deploy + record backup demo

## Running the data generator

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install pandas numpy
python scripts/synthetic_data_generator.py
```

This writes `backend/data/bgw_01_daily.csv` — 180 days of daily records for
well BGW-01, covering CSS cycle stage, reservoir temperature, viscosity,
production, SOR, energy, SPM/VFD pump settings, motor current, fillage, and
a rule-based rod-floating risk score/label.

All modeling assumptions used to generate this data are documented in
`docs/assumptions.md`.
