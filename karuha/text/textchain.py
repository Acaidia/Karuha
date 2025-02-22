from abc import abstractmethod
from base64 import encodebytes
from pydantic import AnyHttpUrl, BaseModel, model_validator
from typing import Any, ClassVar, Dict, Final, List, Literal, MutableMapping, Optional, SupportsIndex, Type, Union
from typing_extensions import Self

from .drafty import Drafty, DraftyFormat, DraftyExtend, ExtendType, InlineType


class BaseText(BaseModel):
    __slots__ = []

    @abstractmethod
    def to_drafty(self) -> Drafty:
        raise NotImplementedError
    
    def __len__(self) -> int:
        return len(str(self))

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {str(self)!r}>"
    
    @abstractmethod
    def __str__(self) -> str:
        return "unknown"


class _Text(BaseText):
    text: str
    
    def to_drafty(self) -> Drafty:
        start = 0
        fmt = []
        while (p := self.text.find('\n', start)) != -1:
            fmt.append(DraftyFormat(at=p, len=1, tp="BR"))
            start = p + 1
        return Drafty(txt=self.text.replace('\n', ' '), fmt=fmt)
    
    def __len__(self) -> int:
        return len(self.text)
    
    def __str__(self) -> str:
        return self.text


class PlainText(_Text):
    def __init__(self, text: str) -> None:
        super().__init__(text=text)
    
    def __getitem__(self, index: Union[SupportsIndex, slice], /) -> "PlainText":
        return self.__class__(text=self.text[index])


class InlineCode(_Text):
    def to_drafty(self) -> Drafty:
        df = super().to_drafty()
        df.fmt.append(DraftyFormat(at=0, len=len(self), tp="CO"))
        return df
    

class TextChain(BaseText):
    contents: List[BaseText]

    def __init__(self, *args: BaseText) -> None:
        super().__init__(contents=args)  # type: ignore
    
    def __getitem__(self, key: SupportsIndex, /) -> BaseText:
        return self.contents[key]

    def to_drafty(self) -> Drafty:
        if not self.contents:
            return Drafty(txt=" ")
        it = iter(self.contents)
        base = next(it).to_drafty()
        for i in it:
            base += i.to_drafty()
        return base
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.contents}>"

    def __str__(self) -> str:
        return ''.join(str(i) for i in self.contents)


class _Container(BaseText):
    tp_map: ClassVar[Dict[str, Type["_Container"]]] = {}

    type: InlineType
    content: BaseText
    
    def to_drafty(self) -> Drafty:
        df = self.content.to_drafty()
        df.fmt.insert(0, DraftyFormat(at=0, len=len(df.txt), tp=self.type))
        return df
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.content!r}>"
    
    def __str__(self) -> str:
        return str(self.content)

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        tp = getattr(cls, "type", cls.model_fields["type"].default)
        if isinstance(tp, str):
            cls.tp_map[tp] = cls


class Bold(_Container):
    type: Final[InlineType] = "ST"
    

class Italic(_Container):
    type: Final[InlineType] = "EM"
    

class Strikethrough(_Container):
    type: Final[InlineType] = "DL"


class Highlight(_Container):
    type: Final[InlineType] = "HL"


class Hidden(_Container):
    type: Final[InlineType] = "HD"
    

class Row(_Container):
    type: Final[InlineType] = "RW"


class Form(_Container):
    type: Final[InlineType] = "FM"

    su: bool = False

    def to_drafty(self) -> Drafty:
        if not self.su:
            return super().to_drafty()
        drafty = self.content.to_drafty()
        length = len(drafty.txt)
        key = len(drafty.ent)
        drafty.ent.append(DraftyExtend(tp="FM", data={"su": True}))
        drafty.fmt.append(DraftyFormat(at=0, len=length, key=key))
        return drafty


class _ExtensionText(_Text):
    tp_map: ClassVar[Dict[str, Type["_ExtensionText"]]] = {}

    type: ExtendType

    @abstractmethod
    def get_data(self) -> Dict[str, Any]:
        raise NotImplementedError
    
    def to_drafty(self) -> Drafty:
        df = super().to_drafty()
        length = len(self)
        df.fmt.append(DraftyFormat(at=0 if length else -1, len=length))
        df.ent.append(DraftyExtend(tp=self.type, data=self.get_data()))
        return df
    
    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        tp = getattr(cls, "type", cls.model_fields["type"].default)
        if isinstance(tp, str):
            cls.tp_map[tp] = cls


class Link(_ExtensionText):
    type: Final[ExtendType] = "LN"
    url: AnyHttpUrl

    def get_data(self) -> Dict[str, Any]:
        return {"url": self.url}
    

class Mention(_ExtensionText):
    type: Final[ExtendType] = "MN"

    val: str

    def get_data(self) -> Dict[str, Any]:
        return {"val": self.val}
    

class Hashtag(_ExtensionText):
    type: Final[ExtendType] = "HT"

    val: str

    def get_data(self) -> Dict[str, Any]:
        return {"val": self.val}


class Button(_ExtensionText):
    type: Final[ExtendType] = "BN"

    name: Optional[str] = None
    val: Optional[str] = None
    act: Literal["pub", "url", "note"] = "pub"
    ref: Optional[str] = None

    @model_validator(mode="after")
    def validate_ref(self) -> Self:
        if self.ref and self.act != "url":
            raise ValueError("only button with action 'url' have field ref")
        return self

    def get_data(self) -> Dict[str, Any]:
        return self.model_dump(include={"name", "val", "act", "ref"}, exclude_none=True)
    
    def __str__(self) -> str:
        if self.name is None:
            return "<button>"
        if self.val:
            return f"<button {self.name}:{self.val}>"
        return f"<button {self.name}>"


class VideoCall(_ExtensionText):
    type: ExtendType = "VC"

    duration: int
    state: Literal["accepted", "busy", "finished", "disconnected", "missed", "declined"]
    incoming: bool
    aonly: bool

    def get_data(self) -> Dict[str, Any]:
        return self.dict(include={"duration", "state", "incoming", "aonly"})


class _Attachment(_ExtensionText):
    text: str = ""
    type: ExtendType

    mime: str
    name: Optional[str] = None
    value: Optional[str] = None
    ref: Optional[str] = None
    size: Optional[int] = None

    @model_validator(mode="before")
    def convert_raw(cls, data: Any) -> Any:
        if isinstance(data, MutableMapping):
            for k, v in data.items():
                if isinstance(k, str) and isinstance(v, bytes) and k.startswith("raw_"):
                    data[k] = encodebytes(v).decode("ascii")
        return data

    @model_validator(mode="after")
    def check_data(self) -> Self:
        if self.ref is None and self.value is None:
            raise ValueError("no data provided")
        return self

    def get_data(self) -> Dict[str, Any]:
        return self.model_dump(exclude={"text", "type"}, exclude_none=True)
    
    def __str__(self) -> str:
        name = self.__class__.__name__
        if self.ref:
            return f"<{name} from {self.ref}>"
        elif self.value:
            value = self.value
            if len(value) < 20:
                return f"<{name} {value}>"
            return f"<{name} {value[:15]}..{value[-3:]}>"
        return f"<{name}>"


class File(_Attachment):
    type: Final[ExtendType] = "EX"
    
    mime: str = "text/plain"


class Image(_Attachment):
    type: Final[ExtendType] = "IM"

    mime: str = "image/png"
    width: int
    height: int


class Audio(_Attachment):
    type: Final[ExtendType] = "AU"

    mime: str = "audio/aac"
    duration: int
    preview: str


class Video(_Attachment):
    type: Final[ExtendType] = "VD"

    mime: str = "video/webm"
    width: int
    height: int
    duration: int

    premime: Optional[str] = None
    preref: Optional[str] = None
    preview: Optional[str] = None
