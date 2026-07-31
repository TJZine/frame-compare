from collections.abc import Iterator, Mapping
from typing import Any

class VideoFrame:
    def __getitem__(self, key: int) -> object: ...
    @property
    def format(self) -> VideoFormat: ...
    @property
    def props(self) -> Mapping[str, object]: ...

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

class Resize:
    def Bicubic(self, **kwargs: object) -> VideoNode: ...
    def Point(self, **kwargs: object) -> VideoNode: ...

class Std:
    def Expr(self, *, expr: list[str]) -> VideoNode: ...
    def Levels(self, **kwargs: object) -> VideoNode: ...
    def SetFrameProps(self, **kwargs: object) -> VideoNode: ...

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
    def get_frame(self, n: int) -> VideoFrame: ...
    @property
    def std(self) -> Std: ...
    @property
    def resize(self) -> Resize: ...

class Core:
    def __getattr__(self, name: str) -> Any: ...
    @property
    def version_number(self) -> int: ...

core: Core

# Common constants used by the codebase (subset; not exhaustive)
RGB24: int
RGB48: int
RGBS: int
FLOAT: int
INTEGER: int
YUV: int
YUV420P8: int
RGB: int

# Color Range
RANGE_LIMITED: int
RANGE_FULL: int

# Matrix Coefficients
MATRIX_RGB: int
MATRIX_BT709: int
MATRIX_UNSPECIFIED: int
MATRIX_FCC: int
MATRIX_BT470BG: int
MATRIX_SMPTE170M: int
MATRIX_SMPTE240M: int
MATRIX_YCGCO: int
MATRIX_BT2020_NCL: int
MATRIX_BT2020_CL: int
MATRIX_CHROMAN: int
MATRIX_CHROMAL: int
MATRIX_ICTCP: int

# Transfer Characteristics
TRANSFER_BT709: int
TRANSFER_UNSPECIFIED: int
TRANSFER_BT470M: int
TRANSFER_BT470BG: int
TRANSFER_SMPTE170M: int
TRANSFER_SMPTE240M: int
TRANSFER_LINEAR: int
TRANSFER_LOG_100: int
TRANSFER_LOG_316: int
TRANSFER_IEC61966_2_4: int
TRANSFER_BT1361E: int
TRANSFER_IEC61966_2_1: int
TRANSFER_BT2020_10: int
TRANSFER_BT2020_12: int
TRANSFER_ST2084: int
TRANSFER_ST428: int
TRANSFER_ARIB_B67: int

# Color Primaries
PRIMARIES_BT709: int
PRIMARIES_UNSPECIFIED: int
PRIMARIES_BT470M: int
PRIMARIES_BT470BG: int
PRIMARIES_SMPTE170M: int
PRIMARIES_SMPTE240M: int
PRIMARIES_FILM: int
PRIMARIES_BT2020: int
PRIMARIES_ST428: int
PRIMARIES_ST431_2: int
PRIMARIES_ST432_1: int
PRIMARIES_EBU3213E: int
