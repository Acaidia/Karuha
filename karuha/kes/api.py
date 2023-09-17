from .core import kes_msg
from .root import get_root_net


def kes_init() -> None:
    root = get_root_net()
    root.send_message(root, kes_msg.NodeInitializeMessage())


def kes_finalize(*, force: bool = False) -> None:
    root = get_root_net()
    if force:
        root.drop()
    else:
        root.send_message(root, kes_msg.NodeFinalizeMessage())
