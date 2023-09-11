import asyncio

from ..logger import logger
from .core import kes_msg, kes_evt, kes_exc
from .core.node import on
from .core.root import RootNetwork, set_root_net, get_root_net  # noqa


class KESRootNetwork(RootNetwork):
    __slots__ = []

    @on(kes_exc.Exception)
    def on_exception(self, exc: kes_exc.Exception) -> None:
        logger.critical(f"uncaught exception {exc.__class__.__name__}: {exc.text}")
        asyncio.get_running_loop().stop()

    @on(kes_exc.Event)
    async def on_event(self, event: kes_exc.Event) -> None:
        if event not in self.event_map:
            logger.warn(f"unhandled event {event!r}")
        else:
            await super().on_event(event)


root_net = KESRootNetwork()
set_root_net(root_net)
