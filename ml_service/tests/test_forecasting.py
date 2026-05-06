from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest

from service.data.tokamark import (
    ForecastingDataset,
    compute_nrmse,
    prepare_forecasting_dataset,
)
from service.models.forecasting import (
    LSTMForecaster,
    TransformerForecaster,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PAST_LEN = 8
FUTURE_LEN = 4
N_FEATURES = 3
N_SHOTS = 10
SEQ_LEN = 20


def _make_raw_data(seed: int = 42) -> np.ndarray:
    """Synthetic shot data ``(n_shots, seq_len, n_features)``."""
    rng = np.random.RandomState(seed)
    return rng.randn(N_SHOTS, SEQ_LEN, N_FEATURES).astype(np.float32)


def _make_lstm_hp() -> dict:
    return {
        "input_size": N_FEATURES,
        "hidden_size": 16,
        "num_layers": 1,
        "bidirectional": True,
        "dropout": 0.1,
        "attention_heads": 2,
        "forecast_horizon": FUTURE_LEN,
        "n_signals": N_FEATURES,
        "learning_rate": 1e-3,
        "batch_size": 8,
        "epochs": 3,
        "early_stopping_patience": 2,
        "weight_decay": 1e-4,
    }


def _make_transformer_hp() -> dict:
    return {
        "input_size": N_FEATURES,
        "d_model": 16,
        "num_heads": 2,
        "num_layers": 1,
        "dim_feedforward": 32,
        "dropout": 0.1,
        "max_seq_len": 50,
        "forecast_horizon": FUTURE_LEN,
        "n_signals": N_FEATURES,
        "learning_rate": 1e-3,
        "warmup_steps": 5,
        "batch_size": 8,
        "epochs": 3,
        "early_stopping_patience": 2,
        "weight_decay": 1e-4,
    }


# ---------------------------------------------------------------------------
# prepare_forecasting_dataset
# ---------------------------------------------------------------------------


class TestPrepareForecasting:

    def test_shapes(self):
        X = _make_raw_data()
        ds = prepare_forecasting_dataset(X, past_len=PAST_LEN, future_len=FUTURE_LEN)

        assert isinstance(ds, ForecastingDataset)
        assert ds.X_train_past.shape[1] == PAST_LEN
        assert ds.X_train_past.shape[2] == N_FEATURES
        assert ds.X_train_future.shape[1] == FUTURE_LEN
        assert ds.X_train_future.shape[2] == N_FEATURES
        # Train + val + test should cover all windows
        total = (len(ds.X_train_past) + len(ds.X_val_past) + len(ds.X_test_past))
        expected_per_shot = SEQ_LEN - PAST_LEN - FUTURE_LEN + 1
        assert total == N_SHOTS * expected_per_shot

    def test_properties(self):
        X = _make_raw_data()
        ds = prepare_forecasting_dataset(X, past_len=PAST_LEN, future_len=FUTURE_LEN)

        assert ds.n_features == N_FEATURES
        assert ds.past_len == PAST_LEN
        assert ds.future_len == FUTURE_LEN

    def test_seq_too_short(self):
        X = np.random.randn(5, 5, 3).astype(np.float32)
        with pytest.raises(ValueError, match="seq_len"):
            prepare_forecasting_dataset(X, past_len=4, future_len=4)

    def test_wrong_dims(self):
        X = np.random.randn(10, 20).astype(np.float32)
        with pytest.raises(ValueError, match="3-D"):
            prepare_forecasting_dataset(X, past_len=5, future_len=5)


# ---------------------------------------------------------------------------
# compute_nrmse
# ---------------------------------------------------------------------------


class TestComputeNRMSE:

    def test_perfect_prediction(self):
        y = np.random.randn(50, FUTURE_LEN, N_FEATURES)
        result = compute_nrmse(y, y)
        assert result["nrmse_mean"] == pytest.approx(0.0, abs=1e-10)
        assert len(result["nrmse_per_signal"]) == N_FEATURES

    def test_mean_prediction_nrmse_one(self):
        """Predicting the mean should give NRMSE ~ 1.0."""
        rng = np.random.RandomState(42)
        y_true = rng.randn(200, FUTURE_LEN, N_FEATURES)
        y_pred = np.broadcast_to(
            y_true.reshape(-1, N_FEATURES).mean(axis=0),
            y_true.shape,
        ).copy()
        result = compute_nrmse(y_true, y_pred)
        assert result["nrmse_mean"] == pytest.approx(1.0, abs=0.1)

    def test_shape_mismatch(self):
        with pytest.raises(ValueError, match="Shape mismatch"):
            compute_nrmse(np.zeros((10, 5, 3)), np.zeros((10, 5, 2)))

    def test_keys(self):
        y = np.random.randn(20, 4, 3)
        result = compute_nrmse(y, y)
        assert "nrmse_per_signal" in result
        assert "nrmse_mean" in result
        assert "rmse_per_signal" in result
        assert "std_per_signal" in result


# ---------------------------------------------------------------------------
# LSTMForecaster
# ---------------------------------------------------------------------------


class TestLSTMForecaster:

    def test_fit_predict(self):
        X = _make_raw_data()
        ds = prepare_forecasting_dataset(X, past_len=PAST_LEN, future_len=FUTURE_LEN)

        model = LSTMForecaster(hyperparams=_make_lstm_hp())
        metrics = model.fit(
            ds.X_train_past, ds.X_train_future,
            ds.X_val_past, ds.X_val_future,
        )

        assert "final_train_loss" in metrics
        assert "best_val_loss" in metrics
        assert metrics["epochs_trained"] > 0

        preds = model.predict(ds.X_test_past)
        assert preds.shape == (len(ds.X_test_past), FUTURE_LEN, N_FEATURES)

    def test_save_load(self):
        X = _make_raw_data()
        ds = prepare_forecasting_dataset(X, past_len=PAST_LEN, future_len=FUTURE_LEN)

        model = LSTMForecaster(hyperparams=_make_lstm_hp())
        model.fit(ds.X_train_past, ds.X_train_future)

        preds_before = model.predict(ds.X_test_past)

        with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as f:
            path = f.name

        try:
            model.save(path)
            loaded = LSTMForecaster()
            loaded.load(path)

            preds_after = loaded.predict(ds.X_test_past)
            np.testing.assert_allclose(preds_before, preds_after, atol=1e-5)

            meta = loaded.metadata()
            assert meta["architecture"] == "LSTMForecaster"
            assert meta["trained_at"] is not None
            assert meta["dataset_hash"] is not None
        finally:
            os.unlink(path)

    def test_metadata(self):
        model = LSTMForecaster(hyperparams=_make_lstm_hp())
        X = _make_raw_data()
        ds = prepare_forecasting_dataset(X, past_len=PAST_LEN, future_len=FUTURE_LEN)
        model.fit(ds.X_train_past, ds.X_train_future)

        meta = model.metadata()
        assert meta["architecture"] == "LSTMForecaster"
        assert "hyperparameters" in meta
        assert meta["total_parameters"] > 0


# ---------------------------------------------------------------------------
# TransformerForecaster
# ---------------------------------------------------------------------------


class TestTransformerForecaster:

    def test_fit_predict(self):
        X = _make_raw_data()
        ds = prepare_forecasting_dataset(X, past_len=PAST_LEN, future_len=FUTURE_LEN)

        model = TransformerForecaster(hyperparams=_make_transformer_hp())
        metrics = model.fit(
            ds.X_train_past, ds.X_train_future,
            ds.X_val_past, ds.X_val_future,
        )

        assert "final_train_loss" in metrics
        assert "best_val_loss" in metrics
        assert metrics["epochs_trained"] > 0

        preds = model.predict(ds.X_test_past)
        assert preds.shape == (len(ds.X_test_past), FUTURE_LEN, N_FEATURES)

    def test_save_load(self):
        X = _make_raw_data()
        ds = prepare_forecasting_dataset(X, past_len=PAST_LEN, future_len=FUTURE_LEN)

        model = TransformerForecaster(hyperparams=_make_transformer_hp())
        model.fit(ds.X_train_past, ds.X_train_future)

        preds_before = model.predict(ds.X_test_past)

        with tempfile.NamedTemporaryFile(suffix=".pt", delete=False) as f:
            path = f.name

        try:
            model.save(path)
            loaded = TransformerForecaster()
            loaded.load(path)

            preds_after = loaded.predict(ds.X_test_past)
            np.testing.assert_allclose(preds_before, preds_after, atol=1e-5)

            meta = loaded.metadata()
            assert meta["architecture"] == "TransformerForecaster"
            assert meta["trained_at"] is not None
        finally:
            os.unlink(path)

    def test_metadata(self):
        model = TransformerForecaster(hyperparams=_make_transformer_hp())
        X = _make_raw_data()
        ds = prepare_forecasting_dataset(X, past_len=PAST_LEN, future_len=FUTURE_LEN)
        model.fit(ds.X_train_past, ds.X_train_future)

        meta = model.metadata()
        assert meta["architecture"] == "TransformerForecaster"
        assert "hyperparameters" in meta
        assert meta["total_parameters"] > 0
