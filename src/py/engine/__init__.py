"""
业务引擎模块

包含矛盾检测规则引擎、时间对齐引擎、告警引擎等核心业务逻辑。
"""

from .alert_engine import (
    AlertConfig,
    AlertEngine,
    AlertSummary,
    generate_alerts,
)

from .contradiction_engine import Contradiction, ContradictionDetector, detect_contradictions

from .time_aligner import (
    AlignedOrderRecord,
    AlignmentResult,
    TimeAligner,
    align_orders_and_records,
)

__all__ = [
    "AlertConfig",
    "AlertEngine",
    "AlertSummary",
    "Contradiction",
    "ContradictionDetector",
    "detect_contradictions",
    "generate_alerts",
    "AlignedOrderRecord",
    "AlignmentResult",
    "TimeAligner",
    "align_orders_and_records",
]