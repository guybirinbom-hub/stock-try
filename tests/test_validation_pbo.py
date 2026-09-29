"""PBO via CSCV: obvious overfitting (pure noise) vs a genuinely better configuration."""
from __future__ import annotations

import numpy as np
import pytest

from stocktry.validation.pbo import cscv_pbo


def test_noise_strategies_pbo_near_half_or_worse():
    rng = np.random.default_rng(42)
    x = rng.normal(0.0, 0.04, size=(320, 50))  # 50 zero-skill configurations
    res = cscv_pbo(x, s_blocks=16)
    assert res.n_splits == 12870 and res.n_configs == 50 and res.t_used == 320
    assert 0.35 <= res.pbo <= 0.8
    assert len(res.logits) == 12870


def test_genuinely_good_configuration_low_pbo():
    rng = np.random.default_rng(7)
    x = rng.normal(0.0, 0.04, size=(320, 50))
    x[:, 17] += 0.03  # one configuration with a real, persistent edge (monthly Sharpe ~0.75)
    res = cscv_pbo(x, s_blocks=16)
    assert res.pbo < 0.05
    assert res.prob_oos_loss < 0.05


def test_sampling_and_validation():
    rng = np.random.default_rng(1)
    x = rng.normal(0, 0.04, size=(160, 10))
    res = cscv_pbo(x, s_blocks=8, max_splits=30, seed=3)
    assert res.n_splits == 30
    res2 = cscv_pbo(x, s_blocks=8, max_splits=30, seed=3)
    np.testing.assert_array_equal(res.logits, res2.logits)
    with pytest.raises(ValueError):
        cscv_pbo(x[:, :1])
    with pytest.raises(ValueError):
        cscv_pbo(x, s_blocks=7)
