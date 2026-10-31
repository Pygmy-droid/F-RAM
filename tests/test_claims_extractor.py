from fram_core.claims import ClaimType, extract_claims, extract_simple


def test_extract_claims_typed_and_bucketed():
    text = "Alice visited the Clinic on 2024-01-10 and used 3D imaging; 30mm screws were mentioned."
    claims = extract_claims(text, doc_id="doc1", chunk_id=2)
    keys = {c.key for c in claims}
    types = {c.type for c in claims}
    all_buckets = {b for c in claims for b in c.buckets}

    assert "Alice" in keys and "Clinic" in keys
    assert "2024-01-10" in keys
    assert any(t == ClaimType.NumberOrUnit for t in types)
    assert any(t == ClaimType.Date for t in types)
    assert "doc:doc1" in all_buckets
    assert any(b.startswith("layout:doc1:2") for b in all_buckets)


def test_extract_simple_still_returns_claims():
    claims = extract_simple("AlphaBeta used 10% solution")
    keys = {c.key for c in claims}
    assert "AlphaBeta" in keys
    assert any(c.type == ClaimType.NumberOrUnit for c in claims)
