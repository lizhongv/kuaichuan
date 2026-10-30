import os

import pytest

from kuaichuan import utils


def test_fmt_size():
    assert utils.fmt_size(512) == "512 B"
    assert utils.fmt_size(1536) == "1.5 KB"
    assert utils.fmt_size(3 * 1024 ** 3) == "3.0 GB"


def test_fmt_duration():
    assert utils.fmt_duration(65) == "01:05"
    assert utils.fmt_duration(3725) == "1:02:05"


def test_safe_join_blocks_traversal(tmp_path):
    assert utils.safe_join(tmp_path, "a/b.txt").startswith(str(tmp_path))
    with pytest.raises(ValueError):
        utils.safe_join(tmp_path, "../evil.txt")


def test_unique_path(tmp_path):
    p = tmp_path / "照片.jpg"
    assert utils.unique_path(str(p)) == str(p)
    p.write_bytes(b"x")
    assert utils.unique_path(str(p)).endswith("照片 (1).jpg")


def test_iter_files_keeps_folder_structure(tmp_path):
    (tmp_path / "资料" / "子目录").mkdir(parents=True)
    (tmp_path / "资料" / "子目录" / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "单个.txt").write_text("b", encoding="utf-8")
    rels = sorted(rel.replace("\\", "/") for _, rel in
                  utils.iter_files([str(tmp_path / "资料"), str(tmp_path / "单个.txt")]))
    assert rels == ["单个.txt", "资料/子目录/a.txt"]
    assert utils.summarize([str(tmp_path / "资料")]) == (1, 1)


def test_iter_files_skips_missing(tmp_path):
    assert list(utils.iter_files([os.path.join(tmp_path, "不存在")])) == []
