from typing import Any, Mapping, Protocol, Sequence, runtime_checkable


class _FrameLike(Protocol):
    props: Mapping[str, Any]


class _StdCoreOps(Protocol):
    def PlaneStats(
        self,
        clip: "VideoNode",
        plane: int | None = ...,
        prop: str | None = ...,
    ) -> "VideoNode": ...
    def MakeDiff(self, clip_a: "VideoNode", clip_b: "VideoNode") -> "VideoNode": ...
    def Prewitt(self, clip: "VideoNode") -> "VideoNode": ...
    def Expr(self, clips: Sequence["VideoNode"], expr: str) -> "VideoNode": ...
    def Trim(self, clip: "VideoNode", first: int, last: int) -> "VideoNode": ...
    def SelectEvery(
        self,
        clip: "VideoNode",
        cycle: int,
        offsets: Sequence[int],
    ) -> "VideoNode": ...
    def ShufflePlanes(
        self,
        clip: "VideoNode",
        planes: Sequence[int] | int,
        colorfamily: Any,
    ) -> "VideoNode": ...
    def CropRel(
        self,
        clip: "VideoNode",
        left: int = ...,
        top: int = ...,
        right: int = ...,
        bottom: int = ...,
    ) -> "VideoNode": ...
    def AddBorders(
        self,
        clip: "VideoNode",
        left: int = ...,
        right: int = ...,
        top: int = ...,
        bottom: int = ...,
    ) -> "VideoNode": ...
    def SetFrameProps(self, clip: "VideoNode", **props: Any) -> "VideoNode": ...


class _StdBoundOps(Protocol):
    def PlaneStats(
        self,
        plane: int | None = ...,
        prop: str | None = ...,
    ) -> "VideoNode": ...
    def CropRel(
        self,
        left: int = ...,
        top: int = ...,
        right: int = ...,
        bottom: int = ...,
    ) -> "VideoNode": ...
    def SetFrameProps(self, **props: Any) -> "VideoNode": ...


class _ResizeOps(Protocol):
    def Bilinear(
        self,
        clip: "VideoNode",
        *,
        width: int | None = ...,
        height: int | None = ...,
        format: Any | None = ...,
        **kwargs: Any,
    ) -> "VideoNode": ...
    def Point(
        self,
        clip: "VideoNode",
        *,
        width: int | None = ...,
        height: int | None = ...,
        format: Any | None = ...,
        **kwargs: Any,
    ) -> "VideoNode": ...
    def Spline36(
        self,
        clip: "VideoNode",
        *,
        width: int | None = ...,
        height: int | None = ...,
        format: Any | None = ...,
        **kwargs: Any,
    ) -> "VideoNode": ...


class _Core(Protocol):
    std: _StdCoreOps
    resize: _ResizeOps


@runtime_checkable
class VideoNode(Protocol):
    format: Any | None
    width: int
    height: int
    num_frames: int
    core: _Core
    std: _StdBoundOps

    def __getitem__(self, item: slice) -> "VideoNode": ...
    def get_frame(self, index: int) -> _FrameLike: ...


core: _Core
RGB: Any
RGB24: Any
GRAY: Any
GRAY8: Any
GRAY16: Any
GRAY32: Any
MATRIX_RGB: int
MATRIX_BT709: int
RANGE_FULL: int
YUV444P16: Any
