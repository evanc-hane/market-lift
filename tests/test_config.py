import pytest

from marketlift.config import SimulationConfig


def test_scale_presets_are_explicit_and_valid():
    test = SimulationConfig.for_scale("test", seed=7)
    demo = SimulationConfig.for_scale("demo", seed=7)
    full = SimulationConfig.for_scale("full", seed=7)
    assert test.city_count == 2
    assert demo.mean_sessions_per_zone_hour == 20
    assert full.mean_sessions_per_zone_hour == 70
    assert all(config.seed == 7 for config in (test, demo, full))


def test_invalid_simulation_config_fails_fast():
    with pytest.raises(ValueError, match="city_count"):
        SimulationConfig(city_count=1)
    with pytest.raises(ValueError, match="positive"):
        SimulationConfig(mean_sessions_per_zone_hour=0)
