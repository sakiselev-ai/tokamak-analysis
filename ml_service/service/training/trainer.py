from __future__ import annotations

import structlog

from service.models.interface import ModelInterface
from service.models.random_forest import RandomForestModel
from service.models.lstm_attention import LSTMAttentionModel
from service.models.transformer import TransformerModel

logger = structlog.get_logger()

MODEL_REGISTRY: dict[str, type[ModelInterface]] = {
    "random_forest": RandomForestModel,
    "lstm_attention": LSTMAttentionModel,
    "transformer": TransformerModel,
}


def create_model(model_type: str, hyperparams: dict | None = None) -> ModelInterface:
    """Factory for creating model instances."""
    if model_type not in MODEL_REGISTRY:
        raise ValueError(f"Unknown model type: {model_type}. Available: {list(MODEL_REGISTRY.keys())}")
    return MODEL_REGISTRY[model_type](hyperparams)


def load_model(model_type: str, path: str) -> ModelInterface:
    """Load a trained model from file."""
    model = create_model(model_type)
    model.load(path)
    return model
