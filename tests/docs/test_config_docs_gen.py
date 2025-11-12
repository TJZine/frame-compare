from __future__ import annotations

from tools import gen_config_docs


def test_generate_markdown_includes_representative_rows() -> None:
    content = gen_config_docs.generate_markdown()

    assert "| `[analysis].frame_count_dark` | int | `20` |" in content
    assert "| `[runtime].ram_limit_mb` | int | `8000` |" in content
    assert "| `[screenshots].export_range` | str (\"full\"|\"limited\") | `\"full\"` |" in content
