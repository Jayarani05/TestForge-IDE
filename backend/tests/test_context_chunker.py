from pathlib import Path

import pytest

from app.context import (
    ContextChunker,
    ContextChunkingService,
    ContextSourceType,
)
from app.repository import tree_service as tree_service_module


def test_chunk_file_preserves_short_content_and_metadata(
    tmp_path,
):
    repository = tmp_path / "repository"
    test_file = repository / "tests" / "test_sample.py"
    test_file.parent.mkdir(parents=True)
    content = "def test_sample():\n    return 1"
    test_file.write_text(content, encoding="utf-8")

    chunks = ContextChunker(
        chunk_lines=4,
        overlap_lines=1,
    ).chunk_file(
        repository_path=str(repository),
        file_path=str(test_file),
        relative_path="tests\\test_sample.py",
        language="Python",
    )

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.content == content
    assert chunk.repository_path == str(repository)
    assert chunk.file_path == str(test_file)
    assert chunk.relative_path == "tests/test_sample.py"
    assert chunk.source_type is ContextSourceType.TEST
    assert chunk.language == "Python"
    assert chunk.start_line == 1
    assert chunk.end_line == 2
    assert chunk.chunk_type == "test"
    assert chunk.metadata == {
        "file_name": "test_sample.py",
        "extension": ".py",
        "is_test": "True",
        "is_automation": "False",
    }


def test_chunk_file_handles_empty_and_whitespace_input(
    tmp_path,
):
    chunker = ContextChunker(
        chunk_lines=3,
        overlap_lines=1,
    )
    empty_file = tmp_path / "empty.py"
    whitespace_file = tmp_path / "whitespace.py"
    empty_file.write_text("", encoding="utf-8")
    whitespace_file.write_text(
        "   \n\t\n",
        encoding="utf-8",
    )

    assert chunker.chunk_file(
        str(tmp_path),
        str(empty_file),
    ) == []
    assert chunker.chunk_file(
        str(tmp_path),
        str(whitespace_file),
    ) == []


def test_long_file_chunks_preserve_order_boundaries_and_overlap(
    tmp_path,
):
    source_file = tmp_path / "module.py"
    lines = [f"line-{number:02}" for number in range(1, 9)]
    source_file.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )

    chunks = ContextChunker(
        chunk_lines=3,
        overlap_lines=1,
    ).chunk_file(
        repository_path=str(tmp_path),
        file_path=str(source_file),
    )

    assert [
        (chunk.start_line, chunk.end_line)
        for chunk in chunks
    ] == [(1, 3), (3, 5), (5, 7), (7, 8)]
    assert [chunk.content.splitlines() for chunk in chunks] == [
        ["line-01", "line-02", "line-03"],
        ["line-03", "line-04", "line-05"],
        ["line-05", "line-06", "line-07"],
        ["line-07", "line-08"],
    ]

    reconstructed = (
        chunks[0].content.splitlines()
        + [
            line
            for chunk in chunks[1:]
            for line in chunk.content.splitlines()[1:]
        ]
    )
    assert reconstructed == lines
    assert all(
        chunk.relative_path == "module.py"
        and chunk.source_type is ContextSourceType.SOURCE_CODE
        and chunk.language == "Python"
        and chunk.chunk_type == "file_segment"
        for chunk in chunks
    )


def test_repository_chunking_uses_supported_text_files_and_metadata(
    tmp_path,
):
    repository = tmp_path / "fixture"
    (repository / "src").mkdir(parents=True)
    (repository / "node_modules" / "pkg").mkdir(
        parents=True
    )
    source_file = repository / "src" / "main.py"
    source_file.write_text(
        "first\nsecond\nthird\n",
        encoding="utf-8",
    )
    (repository / "src" / "image.png").write_bytes(
        b"\x89PNG\r\n\x1a\n"
    )
    (repository / "node_modules" / "pkg" / "index.py").write_text(
        "generated dependency",
        encoding="utf-8",
    )

    chunks = ContextChunkingService().chunk_repository(
        repository
    )

    assert [chunk.relative_path for chunk in chunks] == [
        "src/main.py"
    ]
    assert chunks[0].content == "first\nsecond\nthird"
    assert chunks[0].repository_path == str(repository.resolve())
    assert chunks[0].language == "Python"
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 3


def test_repository_chunking_skips_binary_and_invalid_utf8_files(
    tmp_path,
):
    repository = tmp_path / "fixture"
    source = repository / "src"
    source.mkdir(parents=True)

    (source / "main.py").write_text(
        "print('safe text')\n",
        encoding="utf-8",
    )
    (source / "image.png").write_bytes(
        b"\x89PNG\r\n\x1a\n"
    )
    (source / "program.exe").write_bytes(
        b"MZ\x00\x00binary executable"
    )
    (source / "opaque.data").write_bytes(
        b"\xff\xfe\xfa\xfb"
    )

    chunks = ContextChunkingService().chunk_repository(
        repository
    )
    direct_chunks = ContextChunker().chunk_repository(
        str(repository)
    )

    assert [chunk.relative_path for chunk in chunks] == [
        "src/main.py"
    ]
    assert chunks[0].content == "print('safe text')"
    assert [
        chunk.relative_path
        for chunk in direct_chunks
    ] == ["src/main.py"]


def test_repository_chunking_excludes_generated_directories_only(
    tmp_path,
):
    repository = tmp_path / "fixture"

    included_files = {
        "src/main.py": "print('source')",
        "README.md": "# Project",
        "pyproject.toml": "[project]\nname = 'fixture'",
        "openapi.yaml": "openapi: 3.0.0",
    }
    excluded_files = {
        "node_modules/pkg/index.js": "dependency",
        "build/generated.py": "build output",
        ".cache/tool/cache.txt": "cache",
        "__pycache__/module.py": "bytecode cache",
        ".nyc_output/report.json": "test coverage output",
    }

    for relative_path, content in {
        **included_files,
        **excluded_files,
    }.items():
        file_path = repository / relative_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

    chunks = ContextChunkingService().chunk_repository(
        repository
    )
    direct_chunks = ContextChunker().chunk_repository(
        str(repository)
    )

    assert {
        chunk.relative_path
        for chunk in chunks
    } == set(included_files)
    assert {
        chunk.content
        for chunk in chunks
    } == set(included_files.values())
    assert {
        chunk.relative_path
        for chunk in direct_chunks
    } == set(included_files)


def test_chunk_file_normalizes_utf8_windows_line_endings(
    tmp_path,
):
    source_file = tmp_path / "windows.txt"
    source_file.write_bytes(
        "first\r\nsecond\r\n".encode("utf-8")
    )

    chunks = ContextChunker().chunk_file(
        repository_path=str(tmp_path),
        file_path=str(source_file),
    )

    assert len(chunks) == 1
    assert chunks[0].content == "first\nsecond"


@pytest.mark.parametrize(
    "read_error",
    [OSError("read failed"), PermissionError("access denied")],
)
def test_chunk_file_skips_unreadable_files(
    tmp_path,
    monkeypatch,
    read_error,
):
    source_file = tmp_path / "unreadable.py"
    source_file.write_text("content", encoding="utf-8")
    original_read_bytes = Path.read_bytes

    def read_bytes(path):
        if path == source_file:
            raise read_error
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", read_bytes)

    assert ContextChunker().chunk_file(
        repository_path=str(tmp_path),
        file_path=str(source_file),
    ) == []


def test_direct_repository_chunking_prunes_symlink_files(
    tmp_path,
    monkeypatch,
):
    repository = (tmp_path / "repository").resolve()
    repository.mkdir()
    symlink_file = repository / "outside.py"
    original_is_symlink = Path.is_symlink

    def is_symlink(path):
        if path == symlink_file:
            return True
        return original_is_symlink(path)

    def simulated_walk(root, *, onerror, followlinks):
        assert followlinks is False
        yield str(root), [], [symlink_file.name]

    monkeypatch.setattr(Path, "is_symlink", is_symlink)
    monkeypatch.setattr(
        tree_service_module.os,
        "walk",
        simulated_walk,
    )

    assert ContextChunker().chunk_repository(
        str(repository)
    ) == []
