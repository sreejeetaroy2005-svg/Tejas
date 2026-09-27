from app.services.simulator import simulate_next_day
from app.services.optimizer import optimize_css_cycle

# 1. Injection Pressure Effect
r1 = simulate_next_day(50.0, "injection", 0.0, 8.0, 42.0, 0.0, 200.0, 1400.0)
r2 = simulate_next_day(50.0, "injection", 0.0, 8.0, 42.0, 0.0, 200.0, 1700.0)
print(f"Injection Pressure 1400 psi -> Temp: {r1['reservoir_temperature_c']} C")
print(f"Injection Pressure 1700 psi -> Temp: {r2['reservoir_temperature_c']} C")

# 2. Soak Duration Trade-off
print("\nSoak Duration Trade-off (200 tonnes, 1400 psi):")
# We need to hack optimize_css_cycle to print all candidates
# We'll just run it and see if we can get all the candidates by re-running with fixed soaks
for soak in [3, 4, 5, 6]:
    res = optimize_css_cycle(60.0, 8.0, 42.0, (200.0, 200.0), (1400.0, 1400.0), (soak, soak))
    c = res["best_cycle_option"]
    print(f"Soak {soak} days -> Cumulative Oil: {c['cumulative_oil_bbl']} bbl, Cutoff reached after {c['production_days']} production days, SOR: {c['final_sor']}")

# 3. Cutoff Rule firing on declining trajectory
from app.services.optimizer import should_cutoff_production
print("\nCutoff Rule Firing Examples:")
print(f"Healthy trajectory (oil=150, cum_steam=600, cum_oil=4000): Cutoff = {should_cutoff_production(150, 600, 4000)}")
print(f"Declining trajectory (oil=10, cum_steam=600, cum_oil=1500): Cutoff = {should_cutoff_production(10, 600, 1500)}")
