from pathlib import Path
from textwrap import dedent

from fram_layout.code_chunker import chunk_code, to_snippet_dicts
from fram_layout.assembler import assemble


SAMPLE_CODE = dedent(
    '''
    """Module doc"""

    import os

    class Foo:
        def method(self):
            return 1

    def top():
        return Foo().method()
    '''
)


def _write_tmp(tmp_path: Path) -> Path:
    path = tmp_path / "sample.py"
    path.write_text(SAMPLE_CODE, encoding="utf-8")
    return path


def test_chunk_code_emits_functions(tmp_path):
    path = _write_tmp(tmp_path)
    snippets = chunk_code(path)
    names = [snippet.name for snippet in snippets]
    assert f"{path.stem}" in names
    assert f"{path.stem}.Foo" in names
    assert f"{path.stem}.Foo.method" in names
    assert f"{path.stem}.top" in names


def test_code_snippets_assemble_with_hierarchy(tmp_path):
    path = _write_tmp(tmp_path)
    snippets = to_snippet_dicts(chunk_code(path))
    assembled = assemble(snippets)
    module_header = f"[doc:{path.stem} :: code:{path.stem}]"
    assert module_header in assembled
    assert "Module doc" in assembled
    assert f"[doc:{path.stem} :: code:{path.stem}.Foo]" in assembled
    assert "def method" in assembled


def test_code_chunker_includes_function_docstring(tmp_path):
    code = dedent(
        '''
        def alpha():
            """Alpha doc"""
            return 1
        '''
    )
    path = tmp_path / "snippet.py"
    path.write_text(code, encoding="utf-8")
    snippets = chunk_code(path)
    alpha = next(snippet for snippet in snippets if snippet.name.endswith(".alpha"))
    assert "def alpha" in alpha.text
    assert "Alpha doc" in alpha.text


def test_code_chunker_groups_imports_and_constants(tmp_path):
    code = dedent(
        '''
        """Module doc"""
        import os
        import sys

        ANSWER = 42

        def alpha():
            return ANSWER
        '''
    )
    path = tmp_path / "snippet.py"
    path.write_text(code, encoding="utf-8")
    snippets = chunk_code(path)
    module = next(snippet for snippet in snippets if snippet.name == path.stem)
    assert "import os" in module.text
    assert "ANSWER = 42" in module.text


def test_code_chunker_stable_function_segments(tmp_path):
    base = dedent(
        '''
        def alpha():
            return 1

        def beta():
            return 2
        '''
    )
    modified = dedent(
        '''
        # comment inserted
        def alpha():
            return 1

        def beta():
            return 2
        '''
    )
    base_path = tmp_path / "base.py"
    mod_path = tmp_path / "mod.py"
    base_path.write_text(base, encoding="utf-8")
    mod_path.write_text(modified, encoding="utf-8")

    base_snippets = {
        s.name.split(".")[-1]: s.text for s in chunk_code(base_path) if s.name.endswith((".alpha", ".beta"))
    }
    mod_snippets = {
        s.name.split(".")[-1]: s.text for s in chunk_code(mod_path) if s.name.endswith((".alpha", ".beta"))
    }
    assert base_snippets == mod_snippets
