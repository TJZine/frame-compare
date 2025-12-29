from collections.abc import Iterator
from typing import Any

class VideoFormat:
    id: int
    name: str
    color_family: int
    sample_type: int
    bits_per_sample: int
    bytes_per_sample: int
    subsampling_w: int
    subsampling_h: int
    num_planes: int

class VideoNode:
    def __getitem__(self, key: int | slice) -> VideoNode: ...
    def __iter__(self) -> Iterator[VideoNode]: ...
    @property
    def format(self) -> VideoFormat: ...
    @property
    def width(self) -> int: ...
    @property
    def height(self) -> int: ...
    @property
    def num_frames(self) -> int: ...
    @property
    def fps_num(self) -> int: ...
    @property
    def fps_den(self) -> int: ...
    def set_output(self, index: int = 0) -> None: ...

class Core:
    def __getattr__(self, name: str) -> Any: ...
    @property
    def version_number(self) -> int: ...

core: Core
