# Tejas — Heavy-Oil Digital Twin (SIH Prototype)

> **Decision-support system** for a heavy-oil well (BGW-01) coordinating
> Cyclic Steam Stimulation (CSS) and Sucker Rod Pump (SRP) operations.

**This is a demonstration prototype using synthetic data.** It is not connected
to real Oil India field systems and does not perform autonomous control — all
recommendations require operator review.

![Dashboard](https://img.shields.io/badge/Dashboard-Next.js-black) ![Backend](https://img.shields.io/badge/Backend-FastAPI-green) ![ML](https://img.shields.io/badge/ML-XGBoost+%7C+RF-orange) ![Tests](https://img.shields.io/badge/Tests-87-passing-brightgreen)

---

## What Tejas Solves

Heavy-oil wells produce via two coordinated operations:

1. **CSS (Cyclic Steam Stimulation)** — injecting steam to heat thick oil so it flows
2. **SRP (Sucker Rod Pump)** — mechanical pump that lifts oil to the surface

The core problem: **pump settings don't auto-adjust as the reservoir cools**, leading to rod-floating risk, wasted energy, and lost production.

Tejas provides:
- 📊 **Real-time risk scoring** (0–100) from fillage, viscosity, SPM, motor current
- 🤖 **ML-powered 7-day forecast** of reservoir temperature and oil production
- 🔍 **Dynamometer card classifier** detecting Normal / Rod Floating / Fluid Pound / Gas Interference
- ⚡ **Optimizer** that grid-searches 1,287 SPM/VFD/steam combinations to find the best operating point
- 🎛️ **What-if simulator** to explore parameter changes before applying them
- 📋 **Plain-language explanations** for every recommendation

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                        │
│               localhost:3000 · 7 dashboard tabs              │
│  Overview · Production · SRP · Optimize · Simulate · Forecast │
└──────────────────────────────┬──────────────────────────────┘
                               │ fetch()
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  Backend (FastAPI)                           │
│             localhost:8000 · 8 API endpoints                 │
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌────────────┐ ┌──────────────┐ │
│  │ Risk     │ │Optimize  │ │ Simulator  │ │  Forecast    │ │
│  │ Engine   │ │ Grid     │ │ Physics    │ │  (XGBoost)   │ │
│  └──────────┘ └──────────┘ └────────────┘ └──────────────┘ │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │         Dynacard Classifier (RandomForest)           │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────────────┬──────────────────────────────┘
                               │ reads
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                   Data Layer (CSV)                           │
│  bgw_01_daily.csv (180 days) · dynacards_synthetic_v1.csv   │
└─────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, TypeScript, Tailwind CSS, Recharts, Lucide icons |
| Backend | Python 3.12+, FastAPI, Uvicorn, Pydantic v2 |
| ML | XGBoost (forecast), scikit-learn RandomForest (dynacard classifier) |
| Data | Pandas, synthetic CSV (no database) |
| Testing | pytest (87 tests), Next.js build verification |

---

## Quick Start

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Train ML models
python scripts/train_forecast_model.py
python scripts/train_dynacard_classifier.py

# Start the server
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Swagger docs:** http://localhost:8000/docs

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

**Dashboard:** http://localhost:3000/dashboard

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/wells` | List all wells with status |
| GET | `/api/wells/{id}` | Single well snapshot |
| GET | `/api/wells/{id}/history?days=90` | Time series for charts |
| GET | `/api/wells/{id}/forecast?days=7` | **ML forecast** — 7-day temperature + production |
| POST | `/api/simulate` | **What-if** — override SPM/VFD/steam/soak |
| POST | `/api/optimize/{well_id}` | **Optimizer** — grid search with explanation |
| GET | `/api/dynacards/examples` | 4 example pump cards (one per condition) |
| POST | `/api/dynacards/classify` | **ML classifier** — diagnose a pump card |

---

## ML Models

### 1. 7-Day Reservoir Forecast (XGBoost)

Two XGBoost regressors predict temperature and oil production day-by-day for 7 days, fed recursively.

| Model | MAE | R² |
|-------|-----|-----|
| Temperature | 1.53 °C | 0.96 |
| Production | 8.81 bbl/day | 0.94 |

### 2. Dynamometer Card Classifier (RandomForest)

Classifies pump card shapes into 4 conditions from 13 features (6 geometric + 7 operating).

| Condition | Precision | Recall |
|-----------|-----------|--------|
| Normal | 72% | 94% |
| Rod Floating | 89% | 89% |
| Fluid Pound | 100% | 93% |
| Gas Interference | 60% | 21% |

**Overall accuracy:** 80% on 400 synthetic pump card samples.

---

## Risk Score Formula

Transparent, rule-based scoring — not a black box:

```
risk = 0.35 × fillage_component      (how empty the pump is)
     + 0.30 × viscosity_component    (how thick the oil is)
     + 0.20 × spm_excess_component   (pump running too fast)
     + 0.15 × motor_current_component (motor straining)
```

| Label | Range | Color |
|-------|-------|-------|
| Low | ≤ 35 | 🟢 Green |
| Medium | 36–65 | 🟡 Amber |
| High | > 65 | 🔴 Red |

---

## Dashboard Tabs

| Tab | What it shows |
|-----|---------------|
| **Overview** | 5 KPI cards, risk assessment with contributing factors, optimization recommendation, intro banner, Reset Demo button |
| **Production** | Oil rate trend, reservoir temperature, viscosity, CSS stage timeline, 7-day forecast chart with uncertainty bands |
| **SRP Health** | SPM/VFD trend, motor current chart, fillage gauge, dynamometer card visualization with condition classifier |
| **Optimize** | Current vs recommended settings side-by-side, KPI comparison, "Why?" explanation panel |
| **What-If Simulator** | Sliders for steam volume, soak time, SPM, VFD — calls POST /api/simulate, shows before/after KPIs |
| **Dynacards** | Reference gallery of 4 condition types, overlay comparison, interactive classifier with confidence and features |

---

## Design System

- **Colors:** Dark navy background, amber accents, green = safe, amber = attention, red = danger
- **Tooltips:** Every technical metric has an (i) info tooltip with a plain-language explanation
- **Units:** All numbers display units (°C, psi, cP, bbl/day, kWh, SPM, Hz)
- **Rounding:** 1–2 decimal places, no raw floats
- **Offline mode:** Dashboard renders with mock data if backend is unreachable

---

## Running Tests

```bash
cd backend
python -m pytest tests/ -v
```

**87 tests** covering: risk engine (10), optimizer (12), simulator (18), wells API (12), forecast (11), dynacard classifier (14), input validation (10).

---

## Project Structure

```
tejas/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entrypoint
│   │   ├── models.py            # Pydantic response/request models
│   │   ├── routers/             # API route definitions
│   │   │   ├── wells.py         # Wells, history, forecast endpoints
│   │   │   ├── optimize.py      # Optimization endpoint
│   │   │   ├── simulate.py      # What-if simulation endpoint
│   │   │   └── dynacards.py     # Dynamometer card endpoints
│   │   └── services/            # Business logic
│   │       ├── data_service.py  # CSV loading, data access
│   │       ├── risk_engine.py   # Risk scoring formula
│   │       ├── optimizer.py     # Grid search optimizer
│   │       ├── simulator.py     # Physics-based simulation
│   │       ├── forecast_service.py  # XGBoost 7-day forecast
│   │       └── dynacard_service.py  # RandomForest classifier
│   ├── scripts/
│   │   ├── synthetic_data_generator.py  # Generate daily data
│   │   ├── train_forecast_model.py      # Train XGBoost models
│   │   └── train_dynacard_classifier.py # Train RandomForest
│   ├── models/                  # Saved ML models (.pkl)
│   ├── data/                    # Synthetic CSV files
│   └── tests/                   # 87 pytest tests
├── frontend/
│   ├── src/
│   │   ├── app/dashboard/       # 6 dashboard pages
│   │   ├── components/          # Reusable UI components
│   │   ├── lib/                 # API client, mock data, tooltips
│   │   └── types/               # TypeScript type definitions
│   └── public/                  # Static assets
├── docs/
│   └── assumptions.md           # Modeling assumptions
└── README.md
```

---

## Data Disclaimer

All data in this prototype is **synthetic** — generated from physics-based models, not real Oil India field data. The dynacard dataset contains 400 synthetic pump card shapes across 20 wells. Risk formulas and thresholds are simplified approximations for demonstration purposes.

---

## License

This is a prototype built for SIH (Smart India Hackathon) demonstration purposes.
