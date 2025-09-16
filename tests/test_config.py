from pathlib import Path
import pytest
from src.config_loader import load_config, ConfigError

def _copy_default_config(tmp_path: Path) -> Path:
    cfg_src = Path(__file__).resolve().parents[1] / "config.toml"
    cfg_dst = tmp_path / "config.toml"
    cfg_dst.write_text(cfg_src.read_text(encoding="utf-8"), encoding="utf-8")
    return cfg_dst

def test_load_defaults(tmp_path: Path):
    cfg_path = _copy_default_config(tmp_path)
    app = load_config(str(cfg_path))
    assert app.analysis.frame_count_dark > 0
    assert app.analysis.frame_data_filename
    assert app.screenshots.directory_name
    assert app.runtime.ram_limit_mb == 8000
    assert app.overrides.trim == {}

def test_invalid_ram_limit(tmp_path: Path):
    cfg_path = _copy_default_config(tmp_path)
    cfg_text = cfg_path.read_text(encoding="utf-8").replace("ram_limit_mb = 8000", "ram_limit_mb = 0")
    cfg_path.write_text(cfg_text, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(str(cfg_path))

def test_invalid_change_fps(tmp_path: Path):
    cfg_path = _copy_default_config(tmp_path)
    cfg_text = cfg_path.read_text(encoding="utf-8").replace("change_fps = {}", "change_fps = { sample = \"oops\" }")
    cfg_path.write_text(cfg_text, encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(str(cfg_path))

def test_valid_change_fps(tmp_path: Path):
    cfg_path = _copy_default_config(tmp_path)
    cfg_text = cfg_path.read_text(encoding="utf-8").replace("change_fps = {}", "change_fps = { sample = [24000, 1001], rest = \"set\" }")
    cfg_path.write_text(cfg_text, encoding="utf-8")
    app = load_config(str(cfg_path))
    assert app.overrides.change_fps["sample"] == [24000, 1001]
    assert app.overrides.change_fps["rest"] == "set"
