"""Closed-form ridge regression on standardised features (numpy only)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RidgeModel:
    means: np.ndarray
    scales: np.ndarray
    coefficients: np.ndarray  # on standardised features
    intercept: float

    def predict(self, features: np.ndarray) -> np.ndarray:
        standardised = (np.asarray(features, dtype=float) - self.means) / self.scales
        return standardised @ self.coefficients + self.intercept

    def contributions(self, features: np.ndarray) -> np.ndarray:
        """Per-feature contribution relative to the training mean."""
        return (np.asarray(features, dtype=float) - self.means) / self.scales * self.coefficients


def fit_ridge(features: np.ndarray, target: np.ndarray, alpha: float = 1.0) -> RidgeModel:
    x = np.asarray(features, dtype=float)
    y = np.asarray(target, dtype=float)
    if x.ndim != 2 or len(x) != len(y) or len(y) == 0:
        raise ValueError("features must be a non-empty 2-D array aligned with target")
    means = x.mean(axis=0)
    scales = x.std(axis=0)
    scales = np.where(scales == 0, 1.0, scales)
    z = (x - means) / scales
    intercept = float(y.mean())
    gram = z.T @ z + alpha * np.eye(z.shape[1])
    coefficients = np.linalg.solve(gram, z.T @ (y - intercept))
    return RidgeModel(means=means, scales=scales, coefficients=coefficients, intercept=intercept)
