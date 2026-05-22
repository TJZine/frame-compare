"""Tests for config utilities."""

from __future__ import annotations

from frame_compare.config.utils import deep_merge


def test_deep_merge_basic_and_override() -> None:
    base: dict[str, object] = {"a": 1, "b": 2, "c": 3}
    updates: dict[str, object] = {"b": 20, "d": 4}

    result = deep_merge(base, updates)
    assert result == {"a": 1, "b": 20, "c": 3, "d": 4}


def test_deep_merge_recursive() -> None:
    base: dict[str, object] = {
        "section1": {
            "key1": "value1",
            "key2": "value2",
        },
        "section2": {
            "key3": "value3",
        },
    }
    updates: dict[str, object] = {
        "section1": {
            "key2": "value2-updated",
            "key4": "value4",
        },
        "section2": "scalar-override",
    }

    result = deep_merge(base, updates)
    assert result == {
        "section1": {
            "key1": "value1",
            "key2": "value2-updated",
            "key4": "value4",
        },
        "section2": "scalar-override",
    }


def test_deep_merge_does_not_mutate_input_mappings() -> None:
    base: dict[str, object] = {
        "section1": {
            "key1": "value1",
        },
        "a": 1,
    }
    updates: dict[str, object] = {
        "section1": {
            "key1": "value1-updated",
        },
        "b": 2,
    }

    # Run deep_merge
    result = deep_merge(base, updates)

    # Assert result is correct
    assert result == {
        "section1": {
            "key1": "value1-updated",
        },
        "a": 1,
        "b": 2,
    }

    # Verify inputs were not mutated
    assert base == {
        "section1": {
            "key1": "value1",
        },
        "a": 1,
    }
    assert updates == {
        "section1": {
            "key1": "value1-updated",
        },
        "b": 2,
    }
