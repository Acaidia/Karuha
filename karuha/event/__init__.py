from typing import Any, Callable, Type, TypeVar

from .base import Event
from .bot import BotEvent, ClientEvent, PublishEvent, SubscribeEvent, LeaveEvent, ServerEvent, DataEvent, CtrlEvent, MetaEvent, PresEvent, InfoEvent
from . import handler


T_Event = TypeVar("T_Event", bound=Event)


def on(event: Type[T_Event]) -> Callable[[Callable[[T_Event], Any]], Callable[[T_Event], Any]]:
    def wrapper(func: Callable[[T_Event], Any]) -> Callable[[T_Event], Any]:
        event.add_handler(func)
        return func
    return wrapper


__all__ = [
    "Event",
    "BotEvent",

    "ClientEvent",
    "PublishEvent",
    "SubscribeEvent",
    "LeaveEvent",

    "ServerEvent",
    "DataEvent",
    "CtrlEvent",
    "MetaEvent",
    "PresEvent",
    "InfoEvent"
]