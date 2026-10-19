"""Session-local numeric pins and opening-offset hints; no viewer or persistence access."""

from __future__ import annotations

from dataclasses import dataclass, replace

from frame_compare.vsview.alignment_review_contract import AlignmentReviewComparisonMetadata


@dataclass(frozen=True, slots=True)
class OpeningHint:
    offset: int | None
    provisional: bool = False


def opening_hint(comparison: AlignmentReviewComparisonMetadata) -> OpeningHint:
    authority = comparison.audio_review.current_authority.frame_offset
    if authority is not None:
        return OpeningHint(authority)
    attempt = comparison.audio_review.audio_attempt
    if attempt is not None and attempt.decision.state == "provisional":
        candidate = attempt.decision.candidate
        if candidate is not None:
            return OpeningHint(candidate.frame_offset, provisional=True)
    return OpeningHint(None)


@dataclass(frozen=True, slots=True)
class Prediction:
    frame: int | None
    description: str


@dataclass(frozen=True, slots=True)
class SelectedCohort:
    counts: tuple[int, ...]
    selected: tuple[int | None, ...]
    anchor: int | None = None
    revision: int = 0

    @classmethod
    def empty(cls, counts: tuple[int, ...], *, revision: int = 0) -> SelectedCohort:
        return cls(counts, (None,) * len(counts), revision=revision)

    def _validate(self, index: int, frame: int) -> None:
        if (
            isinstance(index, bool)
            or not 0 <= index < len(self.counts)
            or isinstance(frame, bool)
            or not 0 <= frame < self.counts[index]
        ):
            raise ValueError("selected source/frame is outside its source")

    def needs_new_moment(self, index: int, frame: int) -> bool:
        self._validate(index, frame)
        return self.anchor is not None and self.selected[index] != frame

    def set_anchor(self, index: int, frame: int) -> SelectedCohort:
        self._validate(index, frame)
        pins: list[int | None] = (
            list(self.selected)
            if not self.needs_new_moment(index, frame)
            else [None] * len(self.counts)
        )
        pins[index] = frame
        return replace(self, selected=tuple(pins), anchor=index, revision=self.revision + 1)

    def select(self, index: int, frame: int) -> SelectedCohort:
        self._validate(index, frame)
        if self.anchor is None or index == self.anchor:
            raise ValueError("choose an anchor or explicitly choose a new anchor moment")
        pins = list(self.selected)
        pins[index] = frame
        return replace(self, selected=tuple(pins), revision=self.revision + 1)

    def clear(self, index: int) -> SelectedCohort:
        if not 0 <= index < len(self.counts):
            raise ValueError("unknown source")
        if index == self.anchor:
            return self.reset()
        pins = list(self.selected)
        pins[index] = None
        return replace(self, selected=tuple(pins), revision=self.revision + 1)

    def reset(self) -> SelectedCohort:
        return self.empty(self.counts, revision=self.revision + 1)

    def predict(self, index: int, hints: tuple[OpeningHint, ...]) -> Prediction:
        if self.anchor is None:
            return Prediction(None, "Choose an anchor")
        frame = self.selected[self.anchor]
        assert frame is not None
        if index == self.anchor:
            return Prediction(frame, f"Anchor frame {frame}")
        own, target = hints[self.anchor], hints[index]
        if own.offset is None or target.offset is None:
            return Prediction(None, "Unavailable opening offset — match manually")
        predicted = frame + own.offset - target.offset
        if not 0 <= predicted < self.counts[index]:
            return Prediction(None, "Prediction outside source range — match manually")
        provenance = (
            "Provisional opening hint"
            if own.provisional or target.provisional
            else "Opening alignment hint"
        )
        return Prediction(predicted, f"Predicted frame {predicted} — {provenance}")
