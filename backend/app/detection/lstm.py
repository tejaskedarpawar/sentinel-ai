"""
AI Threat Detection Engine — LSTM sequence autoencoder (PyTorch).

The Isolation Forest and Autoencoder above score each employee-day in
isolation. That misses slow-drip exfiltration, where no single day
looks alarming but the *trend* across two-plus weeks does. This module
instead treats each employee's full day-by-day feature history as a
sequence: an LSTM encodes the sequence to a fixed vector, a second
LSTM decodes it back out, and the per-day reconstruction error is the
anomaly score — a day (or run of days) the model can't reconstruct
well is a day that breaks from the employee's own longer-run pattern.
"""
import numpy as np
import torch
import torch.nn as nn
from torch.nn.utils.rnn import pad_sequence


class _LSTMAutoencoder(nn.Module):
    def __init__(self, in_dim: int, hidden: int = 16):
        super().__init__()
        self.encoder = nn.LSTM(in_dim, hidden, batch_first=True)
        self.decoder = nn.LSTM(hidden, hidden, batch_first=True)
        self.output_proj = nn.Linear(hidden, in_dim)

    def forward(self, x, lengths):
        packed = nn.utils.rnn.pack_padded_sequence(
            x, lengths.cpu(), batch_first=True, enforce_sorted=False
        )
        _, (h_n, c_n) = self.encoder(packed)
        # Repeat the encoded summary across the sequence length as the
        # decoder's input at every timestep (a simple, robust seq2seq
        # pattern for short sequences like these ~15-30 day histories).
        max_len = x.size(1)
        repeated = h_n[-1].unsqueeze(1).repeat(1, max_len, 1)
        decoded, _ = self.decoder(repeated)
        return self.output_proj(decoded)


class LSTMSequenceDetector:
    """Fits one LSTM autoencoder across all employees' feature-vector
    sequences, then returns a per-employee-day reconstruction-error
    score that specifically rewards catching *trends*, not just
    single-day outliers."""

    def __init__(self, epochs: int = 150, lr: float = 0.01, hidden: int = 16, seed: int = 0):
        self.epochs = epochs
        self.lr = lr
        self.hidden = hidden
        torch.manual_seed(seed)
        self.model = None
        self._mean = None
        self._std = None
        self._max_error = 1.0

    def _standardize(self, arr: np.ndarray) -> np.ndarray:
        return (arr - self._mean) / self._std

    def fit(self, sequences: list[np.ndarray]):
        """`sequences` is a list of (seq_len_i, n_features) arrays, one
        per employee, ordered by date."""
        all_rows = np.concatenate(sequences, axis=0)
        self._mean = all_rows.mean(axis=0)
        self._std = all_rows.std(axis=0)
        self._std[self._std < 1e-6] = 1.0

        tensors = [torch.tensor(self._standardize(s), dtype=torch.float32) for s in sequences]
        lengths = torch.tensor([t.shape[0] for t in tensors])
        padded = pad_sequence(tensors, batch_first=True)  # (batch, max_len, features)

        self.model = _LSTMAutoencoder(in_dim=padded.shape[2], hidden=self.hidden)
        opt = torch.optim.Adam(self.model.parameters(), lr=self.lr)

        mask = torch.arange(padded.shape[1]).unsqueeze(0) < lengths.unsqueeze(1)  # (batch, max_len)
        mask = mask.unsqueeze(-1).float()

        self.model.train()
        for _ in range(self.epochs):
            opt.zero_grad()
            recon = self.model(padded, lengths)
            diff = (recon - padded) ** 2 * mask
            loss = diff.sum() / mask.sum()
            loss.backward()
            opt.step()

        with torch.no_grad():
            recon = self.model(padded, lengths)
            per_step_error = ((recon - padded) ** 2).mean(dim=2).numpy()  # (batch, max_len)
        valid_errors = np.concatenate([per_step_error[i, :lengths[i]] for i in range(len(sequences))])
        self._max_error = max(float(valid_errors.max()), 1e-6)
        self._lengths_cache = lengths
        self._padded_cache = padded
        return self

    def score_all(self, sequences: list[np.ndarray]) -> list[np.ndarray]:
        """Returns a list matching `sequences`, each a (seq_len_i,) array
        of per-day anomaly scores normalised to roughly [0, 1+]."""
        tensors = [torch.tensor(self._standardize(s), dtype=torch.float32) for s in sequences]
        lengths = torch.tensor([t.shape[0] for t in tensors])
        padded = pad_sequence(tensors, batch_first=True)

        self.model.eval()
        with torch.no_grad():
            recon = self.model(padded, lengths)
            per_step_error = ((recon - padded) ** 2).mean(dim=2).numpy()

        return [per_step_error[i, :lengths[i]] / self._max_error for i in range(len(sequences))]
