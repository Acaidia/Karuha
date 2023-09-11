from typing import Optional, Type

from .core import BaseNode, Network, kes_msg
from .root import get_root, set_root


def kes_init(root: Optional[Network] = None) -> None:
    if root is not None:
        set_root(root)
    else:
        root = get_root()
    root.send_message(root, kes_msg.NodeInitializeMessage())


def kes_finalize(*, force: bool = False) -> None:
    root = get_root()
    if force:
        root.drop()
    else:
        root.send_message(root, kes_msg.NodeFinalizeMessage())
