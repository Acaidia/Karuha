from asyncio import iscoroutinefunction
from typing import Any, Callable, Optional

from ..core import Network, Node, kes_msg
from .temp import get_temp_net


class SingletonNode(Node):
    __slots__ = ["__func__", "overload_default"]

    def __init__(
            self,
            net: Network,
            /,
            function: Callable[[kes_msg.Message], Any],
            *,
            overload_default: bool = False,
    ) -> None:
        super().__init__(net)
        self.__func__ = function
        self.overload_default = overload_default
    
    async def __handle_message__(self, message: kes_msg.Message, /, *, raise_for_unsupport: bool = False) -> None:
        if not self.overload_default:
            await super().__handle_message__(message, raise_for_unsupported=False)
        if iscoroutinefunction(self.__func__):
            await self.__func__(message)
        else:
            self.__func__(message)

