from pathlib import Path
from src.config_loader import load_config

def test_load_defaults(tmp_path: Path):
    cfg_src = Path(__file__).resolve().parents[1] / "config.toml"
    cfg_dst = tmp_path / "config.toml"
    cfg_dst.write_text(cfg_src.read_text(encoding="utf-8"), encoding="utf-8")
    app = load_config(str(cfg_dst))
    assert app.analysis.frame_count_dark > 0
    assert app.screenshots.directory_name
