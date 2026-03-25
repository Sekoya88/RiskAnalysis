"""Load trained PPO checkpoint and apply a small score delta to news ranking."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

OBS_DIM = 4
N_ACTIONS = 2

# Default checkpoint relative to repo root (same as `just ppo-train`).
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PPO_CHECKPOINT = _REPO_ROOT / "data" / "ppo_source_policy.pt"

_net: Any = None
_cached_ckpt_path: str | None = None


def ppo_disabled() -> bool:
    """When True, PPO is never loaded (env PPO_DISABLED=1|true|yes)."""
    v = os.getenv("PPO_DISABLED", "").strip().lower()
    return v in ("1", "true", "yes")


def ppo_checkpoint_file_exists() -> bool:
    """True if default or PPO_SOURCE_POLICY_PATH points to an existing file (ignores PPO_DISABLED)."""
    custom = os.getenv("PPO_SOURCE_POLICY_PATH", "").strip()
    if custom:
        return Path(custom).expanduser().is_file()
    return DEFAULT_PPO_CHECKPOINT.is_file()


def resolved_ppo_checkpoint_path() -> str | None:
    """
    Checkpoint to load: not disabled, then PPO_SOURCE_POLICY_PATH if set and exists,
    else data/ppo_source_policy.pt under repo root if it exists.
    """
    if ppo_disabled():
        return None
    custom = os.getenv("PPO_SOURCE_POLICY_PATH", "").strip()
    if custom:
        p = Path(custom).expanduser()
        return str(p.resolve()) if p.is_file() else None
    if DEFAULT_PPO_CHECKPOINT.is_file():
        return str(DEFAULT_PPO_CHECKPOINT.resolve())
    return None


def torch_available() -> bool:
    try:
        import torch  # noqa: F401

        return True
    except ImportError:
        return False


def ppo_policy_effective() -> bool:
    """True if a checkpoint path resolves, PPO not disabled, and PyTorch is importable."""
    return not ppo_disabled() and resolved_ppo_checkpoint_path() is not None and torch_available()


def ppo_policy_active() -> bool:
    """Backward-compatible alias for runtime bar / metrics (effective PPO on)."""
    return ppo_policy_effective()


def _load_net():
    global _net, _cached_ckpt_path
    path = resolved_ppo_checkpoint_path()
    if path is None:
        _net = None
        _cached_ckpt_path = None
        return None
    if not torch_available():
        _net = None
        _cached_ckpt_path = None
        return None
    if _net is not None and _cached_ckpt_path == path:
        return _net
    import torch
    from src.rl.policy_net import ActorCritic

    net = ActorCritic(OBS_DIM, N_ACTIONS)
    try:
        state = torch.load(path, map_location="cpu", weights_only=True)
    except TypeError:
        state = torch.load(path, map_location="cpu")
    net.load_state_dict(state)
    net.train(False)
    _net = net
    _cached_ckpt_path = path
    return _net


def ppo_weight_delta_optional(base_score: float, url: str) -> float:
    """Extra bump to `rl_weight` when a policy checkpoint is available. No-op otherwise."""
    try:
        net = _load_net()
        if net is None:
            return 0.0
        import torch
        from src.rl.features import source_obs_vector

        obs = torch.tensor([source_obs_vector(base_score, url)], dtype=torch.float32)
        with torch.no_grad():
            logits, _ = net(obs)
            action = int(logits.argmax(dim=-1).item())
        delta = float(os.getenv("PPO_SCORE_DELTA", "0.1"))
        return delta if action == 1 else -delta
    except Exception:
        return 0.0
