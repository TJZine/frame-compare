from src.utils import parse_filename_metadata

def test_parse_bracket_group():
    meta = parse_filename_metadata("[Group] Title.S01E02.1080p.mkv", prefer_guessit=False)
    assert meta["file_name"]
    assert {"anime_title","episode_number","episode_title","release_group"} <= set(meta.keys())
