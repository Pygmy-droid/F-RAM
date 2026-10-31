import json, re, sys, unicodedata
from collections import Counter, defaultdict
from pathlib import Path

DOCS_DIR = Path('docs')
OUTPUT_JSON = Path('logs/docs_scan.json')
OUTPUT_TXT = Path('logs/docs_scan_summary.txt')

WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-']*")
ADJ_DUP_RE = re.compile(r"\b(\w+)\s+\1\b", re.IGNORECASE)

def scan_file(path: Path):
    text = path.read_text(encoding='utf-8', errors='replace')
    words = [w.lower() for w in WORD_RE.findall(text)]
    counts = Counter(words)
    duplicates = []
    for i, line in enumerate(text.splitlines(), start=1):
        for m in ADJ_DUP_RE.finditer(line):
            duplicates.append({'line': i, 'text': m.group(0)})
    non_ascii = [ch for ch in text if ord(ch) > 127]
    bad_chars = Counter(ch for ch in non_ascii if ch == '\uFFFD')
    return {
        'file': str(path),
        'word_count': len(words),
        'unique_count': len(counts),
        'top_words': counts.most_common(15),
        'adjacent_duplicates': duplicates,
        'non_ascii_count': len(non_ascii),
        'replacement_char_count': bad_chars.get('\uFFFD', 0),
    }


def main():
    results = []
    if not DOCS_DIR.exists():
        print('docs/ not found', file=sys.stderr)
        sys.exit(2)
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_TXT.parent.mkdir(parents=True, exist_ok=True)
    for p in sorted(DOCS_DIR.rglob('*.md')):
        results.append(scan_file(p))
    for p in sorted(DOCS_DIR.rglob('*.json')):
        results.append(scan_file(p))
    OUTPUT_JSON.write_text(json.dumps(results, indent=2), encoding='utf-8')
    # Write summary focusing on issues
    lines = []
    for r in results:
        if r['adjacent_duplicates'] or r['replacement_char_count'] or r['non_ascii_count']>0:
            lines.append(f"File: {r['file']}")
            if r['adjacent_duplicates']:
                for d in r['adjacent_duplicates'][:10]:
                    lines.append(f"  duplicate: line {d['line']}: {d['text']}")
                if len(r['adjacent_duplicates'])>10:
                    lines.append(f"  ... {len(r['adjacent_duplicates'])-10} more duplicates")
            if r['replacement_char_count']:
                lines.append(f"  replacement chars: {r['replacement_char_count']}")
            if r['non_ascii_count']:
                lines.append(f"  non-ascii chars: {r['non_ascii_count']}")
            lines.append("")
    OUTPUT_TXT.write_text('\n'.join(lines), encoding='utf-8')
    print(f"Wrote {OUTPUT_JSON} and {OUTPUT_TXT}")

if __name__ == '__main__':
    main()
