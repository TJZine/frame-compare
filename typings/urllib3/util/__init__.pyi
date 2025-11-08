from typing import FrozenSet, Iterable


class Retry:
    total: int
    status_forcelist: FrozenSet[int]

    def __init__(
        self,
        total: int = ...,
        backoff_factor: float = ...,
        status_forcelist: Iterable[int] | None = ...,
        allowed_methods: FrozenSet[str] | None = ...,
        raise_on_status: bool = ...,
    ) -> None: ...
