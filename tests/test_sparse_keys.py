from fram_index.sparse_keys import SparseKeyIndex


def test_sparse_key_index_matches_identifiers():
    idx = SparseKeyIndex()
    idx.add("docA", "Order ID ABC-1234 shipped on 2024-01-01")
    idx.add("docB", "Ticket XYZ-9999 pending")

    hits = idx.query("Need details on ABC-1234")
    assert hits == ["docA"]

    # Numeric keys deduplicated
    idx.add("docC", "Invoice 42-77 processed")
    assert "4277" in idx.keys_for_doc("docC")


def test_sparse_key_index_normalizes_identifier_punctuation():
    idx = SparseKeyIndex()
    idx.add("docA", "Order ID ABC-1234 shipped")

    hits = idx.query("Need ABC_1234")
    assert hits == ["docA"]


def test_sparse_key_index_checksum_validation():
    idx = SparseKeyIndex()
    idx.add("docA", "ISBN 97-80-30-6406-157 available")
    idx.add("docB", "ISBN 97-80-30-6406-158 invalid")
    idx.add("docC", "IBAN GB82-WEST-1234-5698-7654-32")
    idx.add("docD", "IBAN GB82-WEST-1234-5698-7654-31")

    assert "9780306406157" in idx.keys_for_doc("docA")
    assert "9780306406158" not in idx.keys_for_doc("docB")
    assert "GB82WEST12345698765432" in idx.keys_for_doc("docC")
    assert "GB82WEST12345698765431" not in idx.keys_for_doc("docD")


def test_sparse_key_index_posting_cap_enforced():
    idx = SparseKeyIndex(postings_cap=2)
    idx.add("docB", "Order ID ABC-1234 shipped")
    idx.add("docA", "Order ID ABC-1234 shipped")
    idx.add("docC", "Order ID ABC-1234 shipped")

    assert idx.query("ABC-1234") == ["docA", "docB"]
