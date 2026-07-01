"""Dialog State Tracking module exports.

Để import components, dùng:
    from dialog_manager import DialogManager, DialogManagementConfig
    from dialog_state_tracker import DialogStateTracker, ProductSlot
"""

from dialog_state_tracker import (
    DialogStateTracker,
    ProductSlot,
    DialogTurn,
    DialogState,
    TopicChangeReason,
)
from dialog_manager import (
    DialogManager,
    DialogManagementConfig,
    check_and_handle_topic_change,
)

__all__ = [
    # Core DST
    "DialogStateTracker",
    "ProductSlot",
    "DialogTurn",
    "DialogState",
    "TopicChangeReason",
    # Manager & Integration
    "DialogManager",
    "DialogManagementConfig",
    "check_and_handle_topic_change",
]

__version__ = "1.0.0"
__author__ = "SearchProductAgent Team"
