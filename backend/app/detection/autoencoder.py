"""
AI Threat Detection Engine — Autoencoder (PyTorch).

A small feed-forward autoencoder is trained to reconstruct each
employee-day's feature vector. It is trained on the *whole* population
(insider threats are rare, so most of the training data is implicitly
normal), and days it reconstructs poorly get a high anomaly score —
exactly the behaviour-baseline-deviation signal the synopsis calls for.
"""
import numpy as np
import torch
import torch.nn as nn


class _AE(nn.Module):
    def __init__(self, in_dim: int, bottleneck: int = 4):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(in_dim, 10), nn.Tanh(),
            nn.Linear(10, bottleneck), nn.Tanh(),
        )
        self.decoder = nn.Sequential(
            nn.Linear(bottleneck, 10), nn.Tanh(),
            nn.Linear(10, in_dim),
        )

    def forward(self, x):
        z = self.encoder(x)
        return self.decoder(z)


class AutoencoderDetector:
    def __init__(self, epochs: int = 200, lr: float = 0.01, seed: int = 0):
        self.epochs = epochs
        self.lr = lr
        torch.manual_seed(seed)
        self.model = None
        self._mean = None
        self._std = None
        self._max_error = 1.0

    def _standardize(self, X: np.ndarray) -> np.ndarray:
        return (X - self._mean) / self._std

    def fit(self, X: np.ndarray):
        self._mean = X.mean(axis=0)
        self._std = X.std(axis=0)
        self._std[self._std < 1e-6] = 1.0

        Xs = self._standardize(X)
        tensor = torch.tensor(Xs, dtype=torch.float32)

        self.model = _AE(in_dim=X.shape[1])
        opt = torch.optim.Adam(self.model.parameters(), lr=self.lr)
        loss_fn = nn.MSELoss()

        self.model.train()
        for _ in range(self.epochs):
            opt.zero_grad()
            recon = self.model(tensor)
            loss = loss_fn(recon, tensor)
            loss.backward()
            opt.step()

        with torch.no_grad():
            recon = self.model(tensor)
            errors = ((recon - tensor) ** 2).mean(dim=1).numpy()
        self._max_error = max(float(errors.max()), 1e-6)
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        """Returns per-row anomaly scores normalised to roughly [0, 1+]
        (values above 1 mean 'worse than anything seen in training')."""
        Xs = self._standardize(X)
        tensor = torch.tensor(Xs, dtype=torch.float32)
        self.model.eval()
        with torch.no_grad():
            recon = self.model(tensor)
            errors = ((recon - tensor) ** 2).mean(dim=1).numpy()
        return errors / self._max_error
