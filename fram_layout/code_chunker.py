"""AST-based code chunker emitting hierarchy metadata (spec §14)."""

from __future__ import annotations

import ast
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Mapping


@dataclass(frozen=True)
class CodeSnippet:
    name: str
    text: str
    index: int

    @property
    def hierarchy(self) -> Mapping[str, str]:
        module = self.name.split(".")[0]
        return {
            "cluster": f"doc:{module}",
            "segment": f"code:{self.name}",
            "chunk": f"chunk:{self.index}",
        }


def chunk_code(path: Path) -> List[CodeSnippet]:
    """Split Python source into module/class/function snippets using AST."""

    source = path.read_text(encoding="utf-8", errors="ignore")
    try:
        tree = ast.parse(source, type_comments=True)
    except SyntaxError:
        return [CodeSnippet(name=path.stem, text=source.strip(), index=0)]

    module = path.stem
    snippets: List[CodeSnippet] = []
    counter = 0

    lines_cache: List[str] = source.splitlines()

    def _segment(node: ast.AST) -> str | None:
        segment = ast.get_source_segment(source, node)
        if segment is not None:
            return segment
        lineno = getattr(node, "lineno", None)
        end_lineno = getattr(node, "end_lineno", None)
        if lineno is None:
            return None
        if end_lineno is None:
            end_lineno = lineno
        start_idx = max(0, lineno - 1)
        end_idx = min(len(lines_cache), end_lineno)
        return "\n".join(lines_cache[start_idx:end_idx])

    def add_snippet(name: str, segment: str | None) -> None:
        nonlocal counter
        if not segment:
            return
        segment = segment.strip()
        if not segment:
            return
        snippets.append(CodeSnippet(name=name, text=segment, index=counter))
        counter += 1

    doc_node = None
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) and isinstance(tree.body[0].value.value, str):
        doc_node = tree.body[0]
        doc_text = _segment(doc_node)
        if doc_text:
            add_snippet(f"{module}.__doc__", doc_text)

    other_segments: deque[str] = deque()

    for node in tree.body:
        if node is doc_node:
            continue
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            seg = _segment(node)
            add_snippet(f"{module}.{node.name}", seg or "")
        elif isinstance(node, ast.ClassDef):
            seg = _segment(node)
            add_snippet(f"{module}.{node.name}", seg or "")
            for body_node in node.body:
                if isinstance(body_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    body_seg = _segment(body_node)
                    add_snippet(f"{module}.{node.name}.{body_node.name}", body_seg or "")
        else:
            seg = _segment(node)
            if seg:
                other_segments.append(seg.strip())

    if other_segments:
        add_snippet(module, "\n\n".join(other_segments))

    if not snippets:
        add_snippet(module, source)

    return snippets


def to_snippet_dicts(snippets: Iterable[CodeSnippet]) -> List[dict]:
    out: List[dict] = []
    for snippet in snippets:
        out.append(
            {
                "kind": "text",
                "text": snippet.text,
                "hierarchy": snippet.hierarchy,
            }
        )
    return out
