"""Small actor–critic for discrete PPO (boost down vs boost up on source score)."""

from __future__ import annotations

import torch
import torch.nn as nn


class ActorCritic(nn.Module):
    def __init__(self, obs_dim: int = 4, n_actions: int = 2) -> None:
        super().__init__()
        self.fc1 = nn.Linear(obs_dim, 64)
        self.fc2 = nn.Linear(64, 64)
        self.policy_head = nn.Linear(64, n_actions)
        self.value_head = nn.Linear(64, 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        z = torch.tanh(self.fc1(x))
        z = torch.tanh(self.fc2(z))
        logits = self.policy_head(z)
        value = self.value_head(z).squeeze(-1)
        return logits, value
