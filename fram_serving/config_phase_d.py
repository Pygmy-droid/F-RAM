# Phase D configuration placeholders
# These keys enable the logistic-alpha and quaternion features (default OFF).

from pydantic import BaseSettings


class PhaseDConfig(BaseSettings):
    enable_logistic_alpha: bool = False
    logistic_r: float = 2.9
    logistic_t_max: int = 3
    enable_quaternion_adapter: bool = False
    quat_weight: float = 0.5
    quat_proj_seed: int = 17
    eval_grid_r: list[float] = [2.6, 2.9, 3.2, 3.5]
    eval_grid_beta: list[float] = [0.0, 0.25, 0.5, 0.75, 1.0]
    eval_grid_tmax: list[int] = [1, 2, 3, 5]
