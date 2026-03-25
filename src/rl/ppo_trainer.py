"""Minimal PPO (clipped surrogate) for single-step source-ranking bandits."""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.optim as optim

from src.rl.policy_net import ActorCritic


class SourcePPOTrainer:
    def __init__(
        self,
        obs_dim: int = 4,
        n_actions: int = 2,
        lr: float = 3e-4,
        clip_eps: float = 0.2,
        vf_coef: float = 0.5,
        ent_coef: float = 0.02,
    ) -> None:
        self.net = ActorCritic(obs_dim, n_actions)
        self.opt = optim.Adam(self.net.parameters(), lr=lr)
        self.clip_eps = clip_eps
        self.vf_coef = vf_coef
        self.ent_coef = ent_coef

    def act(
        self, obs: torch.Tensor, *, deterministic: bool = False
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        logits, value = self.net(obs)
        dist = torch.distributions.Categorical(logits=logits)
        if deterministic:
            action = logits.argmax(dim=-1)
        else:
            action = dist.sample()
        logp = dist.log_prob(action)
        return action, logp, value

    def evaluate(
        self, obs: torch.Tensor, actions: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        logits, value = self.net(obs)
        dist = torch.distributions.Categorical(logits=logits)
        logp = dist.log_prob(actions)
        entropy = dist.entropy()
        return logp, entropy, value

    def update_batch(
        self,
        obs: torch.Tensor,
        actions: torch.Tensor,
        old_logp: torch.Tensor,
        advantages: torch.Tensor,
        returns: torch.Tensor,
        epochs: int = 6,
    ) -> dict[str, float]:
        """One PPO pass over a minibatch (vectorized env steps)."""
        last_pi = 0.0
        last_v = 0.0
        last_ent = 0.0
        for _ in range(epochs):
            logp, entropy, values = self.evaluate(obs, actions)
            ratio = torch.exp(logp - old_logp)
            surr1 = ratio * advantages
            surr2 = torch.clamp(ratio, 1.0 - self.clip_eps, 1.0 + self.clip_eps) * advantages
            policy_loss = -torch.min(surr1, surr2).mean()
            value_loss = nn.functional.mse_loss(values, returns)
            loss = (
                policy_loss
                + self.vf_coef * value_loss
                - self.ent_coef * entropy.mean()
            )
            self.opt.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(self.net.parameters(), 0.5)
            self.opt.step()
            last_pi = float(policy_loss.detach())
            last_v = float(value_loss.detach())
            last_ent = float(entropy.mean().detach())
        return {"policy_loss": last_pi, "value_loss": last_v, "entropy": last_ent}
