import pytest
from app.services.simulator import simulate_next_day
from app.services.optimizer import should_cutoff_production, optimize_css_cycle

def test_injection_pressure_effect():
    """Verify that injection pressure changes the simulated temperature outcome."""
    res_optimal = simulate_next_day(
        current_temp_c=50.0,
        css_stage="injection",
        cycle_prod_progress=0.0,
        spm=8.0,
        vfd_hz=42.0,
        current_sor=0.0,
        steam_volume_tonnes=200.0,
        injection_pressure_psi=1400.0  # optimal
    )
    
    res_suboptimal = simulate_next_day(
        current_temp_c=50.0,
        css_stage="injection",
        cycle_prod_progress=0.0,
        spm=8.0,
        vfd_hz=42.0,
        current_sor=0.0,
        steam_volume_tonnes=200.0,
        injection_pressure_psi=1700.0  # suboptimal
    )
    
    assert res_optimal["reservoir_temperature_c"] > res_suboptimal["reservoir_temperature_c"], "Optimal pressure should yield higher temperature gain"


def test_cutoff_rule():
    """Verify production cutoff logic."""
    # Triggers on low oil + high SOR
    assert should_cutoff_production(oil_bpd=10.0, cumulative_steam=500.0, cumulative_oil=1000.0, min_oil=20.0, max_sor=0.35) == True
    
    # Doesn't trigger on healthy trajectory (high oil, low SOR)
    assert should_cutoff_production(oil_bpd=100.0, cumulative_steam=500.0, cumulative_oil=5000.0, min_oil=20.0, max_sor=0.35) == False


def test_soak_duration_tradeoff():
    """Verify that multiple soak durations are evaluated in the cycle optimization."""
    result = optimize_css_cycle(
        current_temp_c=60.0,
        current_spm=8.0,
        current_vfd=42.0,
        steam_range=(200.0, 200.0),
        pressure_range=(1400.0, 1400.0),
        soak_range=(3, 6)
    )
    
    # We expect 4 candidates because soak_range is 3 to 6
    assert result["alternatives_evaluated"] == 4
    assert result["best_cycle_option"]["soak_time_days"] in [3, 4, 5, 6]
    assert "cutoff_trigger" in result["best_cycle_option"]
