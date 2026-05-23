"""Tests for probe prop key selection and preservation helpers."""

from frame_compare.orchestration.probing import (
    compute_preserved_frame_props,
    compute_tonemap_prop_keys,
    normalize_probe_prop_key,
)


class TestNormalizeProbeProKey:
    """Tests for normalize_probe_prop_key."""

    def test_normalize_probe_prop_key_strips_leading_underscores_and_lowercases(
        self,
    ) -> None:
        """Verify normalization strips leading underscores and lowercases."""
        # Single underscore prefix
        assert normalize_probe_prop_key("_Transfer") == "transfer"

        # Multiple underscore prefixes
        assert normalize_probe_prop_key("__Matrix") == "matrix"
        assert normalize_probe_prop_key("___Primaries") == "primaries"

        # No leading underscores, mixed case
        assert normalize_probe_prop_key("DolbyVision_L6_MaxCLL") == "dolbyvision_l6_maxcll"

        # Already lowercase, no underscores
        assert normalize_probe_prop_key("transfer") == "transfer"

        # Empty string edge case
        assert normalize_probe_prop_key("") == ""

        # Only underscores
        assert normalize_probe_prop_key("___") == ""


class TestComputeTonemapPropKeys:
    """Tests for compute_tonemap_prop_keys."""

    def test_compute_tonemap_prop_keys_selects_expected_keys_and_is_sorted_deterministically(
        self,
    ) -> None:
        """Verify selection rules and deterministic (normalized, key) ordering."""
        frame_props = {
            # Exact matches
            "_Matrix": 1,
            "Transfer": 16,
            "_Primaries": 9,
            "ColorRange": 1,
            # Prefix matches
            "MasteringDisplayPrimaries": b"...",
            "MasteringDisplayLuminance": 1000,
            "ContentLightLevelMax": 1000,
            "ContentLightLevelAverage": 400,
            "DolbyVision_L1_Average": 50,
            "DolbyVision_L6_MaxCLL": 1000,
            # Non-matching keys (should be excluded)
            "SomeOtherProp": "ignored",
            "FrameDuration": 1001,
            "_Colorspace": "not a match",  # "colorspace" is not in exact list
        }

        result = compute_tonemap_prop_keys(frame_props)

        # Should include all matching keys
        expected_keys = {
            "_Matrix",
            "Transfer",
            "_Primaries",
            "ColorRange",
            "MasteringDisplayPrimaries",
            "MasteringDisplayLuminance",
            "ContentLightLevelMax",
            "ContentLightLevelAverage",
            "DolbyVision_L1_Average",
            "DolbyVision_L6_MaxCLL",
        }
        assert set(result) == expected_keys

        # Should be sorted by (normalized, original)
        # Verify ordering: colorrange < contentlightlevelaverage < ...
        sorted_normalized = [normalize_probe_prop_key(k) for k in result]
        assert sorted_normalized == sorted(sorted_normalized)

        # Result is a tuple (immutable)
        assert isinstance(result, tuple)

    def test_compute_tonemap_prop_keys_empty_input(self) -> None:
        """Verify empty input returns empty tuple."""
        assert compute_tonemap_prop_keys({}) == ()

    def test_compute_tonemap_prop_keys_no_matches(self) -> None:
        """Verify no matching keys returns empty tuple."""
        frame_props = {
            "SomeOtherProp": "value",
            "FrameType": "I",
        }
        assert compute_tonemap_prop_keys(frame_props) == ()


class TestComputePreservedFrameProps:
    """Tests for compute_preserved_frame_props."""

    def test_compute_preserved_frame_props_includes_only_tonemap_related_keys(
        self,
    ) -> None:
        """Verify only tonemap-related keys are included, non-tonemap excluded."""
        frame_props = {
            # Tonemap-related, TOML-safe
            "_Matrix": 1,
            "Transfer": 16,
            # Non-tonemap key with TOML-safe value (should be excluded)
            "UnrelatedKey": 1,
            "FrameType": "I",
        }

        result = compute_preserved_frame_props(frame_props)

        # Should include tonemap keys only
        assert "_Matrix" in result
        assert "Transfer" in result

        # Should NOT include non-tonemap keys
        assert "UnrelatedKey" not in result
        assert "FrameType" not in result

    def test_compute_preserved_frame_props_returns_keys_in_sorted_original_key_order(
        self,
    ) -> None:
        """Verify returned dict is populated in sorted original-key order."""
        # Provide keys in unsorted order
        frame_props = {
            "Transfer": 16,
            "_Matrix": 1,
            "_Primaries": 9,
            "ColorRange": 1,
        }

        result = compute_preserved_frame_props(frame_props)

        # Keys should be in lexicographic order (sorted by original key)
        expected_order = ["ColorRange", "Transfer", "_Matrix", "_Primaries"]
        assert list(result.keys()) == expected_order

    def test_compute_preserved_frame_props_drops_non_toml_safe_values(self) -> None:
        """Verify non-TOML-safe values are omitted."""
        frame_props = {
            # TOML-safe values
            "_Matrix": 1,
            "Transfer": 16,
            "ContentLightLevelMax": 1000,
            # Non-TOML-safe values (bytes, object, dict, list)
            "MasteringDisplayPrimaries": b"\x00\x01\x02",
            "MasteringDisplayLuminance": {"min": 0, "max": 1000},
            "DolbyVision_L1_Average": object(),
            # Bool is not considered TOML-safe for this purpose (int subclass)
            "ContentLightLevelAverage": True,
        }

        result = compute_preserved_frame_props(frame_props)

        # Should include TOML-safe primitives
        assert result["_Matrix"] == 1
        assert result["Transfer"] == 16
        assert result["ContentLightLevelMax"] == 1000

        # Should NOT include non-TOML-safe values
        assert "MasteringDisplayPrimaries" not in result
        assert "MasteringDisplayLuminance" not in result
        assert "DolbyVision_L1_Average" not in result
        # Bool is explicitly excluded
        assert "ContentLightLevelAverage" not in result

    def test_compute_preserved_frame_props_persists_dolbyvisionrpu_as_presence_indicator(
        self,
    ) -> None:
        """Verify DolbyVisionRPU key is persisted with value 1, original key preserved."""
        # Test with exact case
        frame_props_exact = {
            "DolbyVisionRPU": b"\x00\x01\x02\x03...",  # Non-primitive blob
            "Transfer": 16,
        }

        result_exact = compute_preserved_frame_props(frame_props_exact)

        # Should persist with original key and value 1
        assert "DolbyVisionRPU" in result_exact
        assert result_exact["DolbyVisionRPU"] == 1
        assert result_exact["Transfer"] == 16

        # Test with normalized variant (leading underscore)
        frame_props_normalized = {
            "_DolbyVisionRPU": object(),  # Non-primitive object
            "_Matrix": 1,
        }

        result_normalized = compute_preserved_frame_props(frame_props_normalized)

        # Should use original key "_DolbyVisionRPU" (not normalized)
        assert "_DolbyVisionRPU" in result_normalized
        assert result_normalized["_DolbyVisionRPU"] == 1
        assert result_normalized["_Matrix"] == 1

        # Verify normalized key is NOT used
        assert "dolbyvisionrpu" not in result_normalized

    def test_compute_preserved_frame_props_empty_input(self) -> None:
        """Verify empty input returns empty dict."""
        assert compute_preserved_frame_props({}) == {}
