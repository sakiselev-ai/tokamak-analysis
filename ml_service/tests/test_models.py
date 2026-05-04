import os
import tempfile

import numpy as np
import pytest

from service.models.random_forest import RandomForestModel
from service.models.lstm_attention import LSTMAttentionModel
from service.models.transformer import TransformerModel
from service.training.trainer import create_model, MODEL_REGISTRY


def test_model_registry():
    assert "random_forest" in MODEL_REGISTRY
    assert "lstm_attention" in MODEL_REGISTRY
    assert "transformer" in MODEL_REGISTRY


def test_create_model():
    model = create_model("random_forest")
    assert isinstance(model, RandomForestModel)


def test_random_forest_fit_predict():
    model = RandomForestModel()
    X = np.random.randn(100, 10)
    y = np.random.randint(0, 2, 100)

    metrics = model.fit(X[:80], y[:80], X[80:], y[80:])
    assert "train_accuracy" in metrics
    assert "val_accuracy" in metrics

    preds = model.predict(X[80:])
    assert preds.shape == (20,)
    assert set(preds).issubset({0, 1})

    proba = model.predict_proba(X[80:])
    assert proba.shape == (20, 2)
    assert np.allclose(proba.sum(axis=1), 1.0)


def test_random_forest_save_load():
    model = RandomForestModel()
    X = np.random.randn(50, 5)
    y = np.random.randint(0, 2, 50)
    model.fit(X, y)

    with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as f:
        path = f.name

    try:
        model.save(path)
        loaded = RandomForestModel()
        loaded.load(path)

        np.testing.assert_array_equal(model.predict(X), loaded.predict(X))
        meta = loaded.metadata()
        assert meta["architecture"] == "RandomForest"
        assert meta["trained_at"] is not None
    finally:
        os.unlink(path)


def test_random_forest_metadata():
    model = RandomForestModel()
    X = np.random.randn(50, 5)
    y = np.random.randint(0, 2, 50)
    model.fit(X, y)

    meta = model.metadata()
    assert meta["architecture"] == "RandomForest"
    assert "hyperparameters" in meta
    assert meta["dataset_hash"] is not None


def test_lstm_attention_create():
    model = LSTMAttentionModel({"input_size": 5, "hidden_size": 16, "num_layers": 1,
                                 "bidirectional": True, "dropout": 0.1, "attention_heads": 2,
                                 "sequence_length": 10, "learning_rate": 1e-3, "batch_size": 8,
                                 "epochs": 2, "early_stopping_patience": 2, "weight_decay": 1e-4})
    X = np.random.randn(20, 10, 5).astype(np.float32)
    y = np.random.randint(0, 2, 20).astype(np.float32)

    metrics = model.fit(X[:16], y[:16], X[16:], y[16:])
    assert "final_train_loss" in metrics

    preds = model.predict(X[16:])
    assert preds.shape == (4,)


def test_transformer_create():
    model = TransformerModel({"input_size": 5, "d_model": 16, "num_heads": 2, "num_layers": 1,
                               "dim_feedforward": 32, "dropout": 0.1, "sequence_length": 10,
                               "learning_rate": 1e-3, "warmup_steps": 5, "batch_size": 8,
                               "epochs": 2, "early_stopping_patience": 2, "weight_decay": 1e-4})
    X = np.random.randn(20, 10, 5).astype(np.float32)
    y = np.random.randint(0, 2, 20).astype(np.float32)

    metrics = model.fit(X[:16], y[:16], X[16:], y[16:])
    assert "final_train_loss" in metrics

    preds = model.predict(X[16:])
    assert preds.shape == (4,)
