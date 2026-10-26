# Well-ID propagation — manual verification checklist

Run through these steps after any change to the well-selector or navigation
to confirm the selected well flows correctly to every tab.

## Setup
1. `npm run dev` (frontend) + `uvicorn app.main:app --reload --port 8000` (backend)
2. Open http://localhost:3000/dashboard/fleet

---

## Test A — Fleet → Well Detail

1. Click any well row in the Fleet table (e.g. **BGW-04**).
2. URL changes to `/dashboard?well=BGW-04`.
3. **Overview tab subtitle** reads  
   ✅ `Real-time status for well BGW-04 — Baghewala field`  
   ❌ ~~`Real-time status for well BGW-01 — ...`~~
4. Top-right status dot shows `BGW-04`.
5. API call in Network tab: `GET /api/wells/BGW-04` (not BGW-01).

## Test B — Tab-by-tab staleness check

With BGW-04 selected (`/dashboard?well=BGW-04`), click each tab and verify:

| Tab | URL | Title shows BGW-04? | API call |
|-----|-----|---------------------|----------|
| Overview | `/dashboard?well=BGW-04` | ✅ subtitle | `GET /api/wells/BGW-04` |
| Production | `/dashboard/production?well=BGW-04` | ✅ subtitle | `GET /api/wells/BGW-04/history` |
| SRP Health | `/dashboard/srp?well=BGW-04` | ✅ subtitle | `GET /api/wells/BGW-04/history` |
| Optimize | `/dashboard/optimize?well=BGW-04` | ✅ well_id in heading | `POST /api/optimize/BGW-04` |
| What-If | `/dashboard/simulate?well=BGW-04` | ✅ subtitle | `GET /api/wells/BGW-04` |
| Dynacards | `/dashboard/dynacards?well=BGW-04` | (no well-specific data) | — |

## Test C — Switching wells clears stale state

1. Open `/dashboard?well=BGW-11` (High-risk well).  
   Overview risk score should be **High / red**.
2. Navigate to fleet, click **BGW-01**.  
   Overview risk score should change to **Low / green** immediately.
3. Check Production tab: history chart data changes (BGW-11 ends in low oil;
   BGW-01 has stable mid-range).

## Test D — Default fallback

1. Open `/dashboard` (no `?well=` param).
2. Behaviour is identical to `/dashboard?well=BGW-01` — BGW-01 is the default.

## Test E — URL bookmarkability

1. Copy the URL `/dashboard/production?well=BGW-07` and open in a new tab.
2. Without navigating from fleet, the page loads with BGW-07 data directly.

---

## Automated check (pytest-backend)

The backend regression test `tests/test_fleet.py::TestExistingWellsUnbroken`
verifies all 12 wells return 200 from `GET /api/wells/{id}`.

To run:
```bash
cd shakti-sih/backend
pytest tests/test_fleet.py::TestExistingWellsUnbroken -v
```

---

## What was fixed (2026-09-27)

| File | Bug | Fix |
|------|-----|-----|
| `dashboard/page.tsx` | `useEffect(…,[])` never re-ran on well change | dep `[wellId]`; use `fetchWell(wellId)` |
| `dashboard/production/page.tsx` | same; used `wells[0]` for well metadata | dep `[wellId]`; use `fetchWell(wellId)` |
| `dashboard/srp/page.tsx` | same | dep `[wellId]`; use `fetchWell(wellId)` |
| `dashboard/optimize/page.tsx` | `useEffect(…,[])` never re-ran | dep `[wellId]` |
| `dashboard/simulate/page.tsx` | no `useWellId`; used `fetchWells()+wells[0]` | added `useWellId`; `fetchWell(wellId)`; resets overrides on well change |
