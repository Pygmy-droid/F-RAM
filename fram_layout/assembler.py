"""Context assembler helpers for layout-aware snippets (§15)."""

from __future__ import annotations

from typing import Any, Iterable, List, Mapping, Optional, Sequence, cast


def _segment_key(snippet: Mapping[str, object]) -> Optional[str]:
    hierarchy = snippet.get("hierarchy")
    if isinstance(hierarchy, Mapping):
        segment = hierarchy.get("segment")
        if segment:
            return str(segment)
        cluster = hierarchy.get("cluster")
        if cluster:
            return str(cluster)
        return "segment:0"
    return None


def _cluster_key(snippet: Mapping[str, object]) -> Optional[str]:
    hierarchy = snippet.get("hierarchy")
    if isinstance(hierarchy, Mapping):
        cluster = hierarchy.get("cluster")
        if cluster:
            return str(cluster)
    return None


def _format_row(values: Sequence[str]) -> str:
    return " | ".join(values)


def assemble(snippets: Iterable[Mapping[str, object]]) -> str:
    """Assemble text chunks ensuring table headers precede their cells."""

    grouped: dict[str, List[Mapping[str, object]]] = {}
    order: List[str] = []
    segment_headers: dict[str, Optional[str]] = {}
    flat_counter = 0
    for snippet in snippets:
        segment = _segment_key(snippet)
        header: Optional[str]
        if segment is None:
            segment = f"flat:{flat_counter}"
            flat_counter += 1
            kind = snippet.get("kind")
            header = None if kind == "table_cell" else "[cluster:unknown :: segment:0]"
        else:
            cluster = _cluster_key(snippet) or "cluster:unknown"
            header = f"[{cluster} :: {segment}]"
        grouped.setdefault(segment, []).append(snippet)
        if segment not in order:
            order.append(segment)
        segment_headers.setdefault(segment, header)

    lines: List[str] = []
    for segment in order:
        header = segment_headers.get(segment)
        if header:
            lines.append(header)
        for snippet in grouped[segment]:
            kind = snippet.get("kind")  # type: ignore[attr-defined]
            if kind == "table_cell":
                headers = cast(Sequence[str], snippet.get("headers", ()))
                row = cast(Sequence[str], snippet.get("row", ()))
                header_line = _format_row(list(headers))
                if not lines or lines[-1] != header_line:
                    lines.append(header_line)
                lines.append(_format_row(list(row)))
            else:
                text = cast(Any, snippet.get("text", ""))
                if text:
                    lines.append(str(text))
    return "\n".join(lines)
