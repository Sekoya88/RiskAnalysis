#!/usr/bin/env python3
"""Train PPO policy on URL feedback votes (Postgres or SQLite). Requires `torch` (requirements-rl.txt)."""

from __future__ import annotations

import argparse
import os
import random
import sys

import torch

from src.db import get_source_feedback_score, list_feedback_votes
from src.rl.features import source_obs_vector
from src.rl.ppo_trainer import SourcePPOTrainer


def _synthetic_votes(n: int = 256, seed: int = 0) -> list[tuple[str, bool]]:
    rng = random.Random(seed)
    out: list[tuple[str, bool]] = []
    for i in range(n):
        u = f"https://example.com/article/{i}/{rng.randint(0, 9999)}"
        out.append((u, rng.random() > 0.45))
    return out


def _build_batch(
    votes: list[tuple[str, bool]], batch_size: int, rng: random.Random
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    batch = [votes[rng.randrange(len(votes))] for _ in range(batch_size)]
    obs_list: list[list[float]] = []
    labels: list[int] = []
    for url, helpful in batch:
        base = get_source_feedback_score(url)
        obs_list.append(source_obs_vector(base, url))
        labels.append(1 if helpful else 0)
    obs = torch.tensor(obs_list, dtype=torch.float32)
    label_t = torch.tensor(labels, dtype=torch.int64)
    return obs, label_t


def main() -> int:
    ap = argparse.ArgumentParser(description="Train PPO source-ranking policy from feedback table.")
    ap.add_argument("--steps", type=int, default=2000, help="Number of PPO updates (batch each step).")
    ap.add_argument("--batch-size", type=int, default=64)
    ap.add_argument("--save", type=str, default="data/ppo_source_policy.pt")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument(
        "--skip-if-exists",
        action="store_true",
        help="Exit 0 without training if --save already exists.",
    )
    args = ap.parse_args()
    save_path = os.path.abspath(args.save)
    if args.skip_if_exists and os.path.isfile(save_path):
        print(f"Skip training — checkpoint exists: {save_path}", file=sys.stderr)
        return 0

    rng = random.Random(args.seed)
    torch.manual_seed(args.seed)

    votes = list_feedback_votes()
    if len(votes) < 16:
        print(f"Only {len(votes)} feedback rows — mixing in synthetic votes for stability.", file=sys.stderr)
        votes = votes + _synthetic_votes(256 - len(votes), seed=args.seed)

    trainer = SourcePPOTrainer()
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    for step in range(args.steps):
        obs, label_t = _build_batch(votes, args.batch_size, rng)
        action, logp_old, val_old = trainer.act(obs, deterministic=False)
        # Detach sampling graph so update_batch can run multiple PPO epochs without double-backward.
        action = action.detach()
        logp_old = logp_old.detach()
        reward = torch.where(action == label_t, torch.ones_like(action, dtype=torch.float32), -0.35 * torch.ones_like(action, dtype=torch.float32))
        advantages = reward - val_old.detach()
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)
        returns = reward
        stats = trainer.update_batch(obs, action, logp_old, advantages, returns, epochs=4)
        if step % 200 == 0 or step == args.steps - 1:
            with torch.no_grad():
                acc = float((action == label_t).float().mean())
            print(f"step {step:5d} acc={acc:.3f} pi={stats['policy_loss']:.4f} v={stats['value_loss']:.4f}")

    torch.save(trainer.net.state_dict(), save_path)
    print(f"Wrote {save_path}")
    print("Loaded automatically at runtime unless PPO_DISABLED=1 (default path data/ppo_source_policy.pt).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
