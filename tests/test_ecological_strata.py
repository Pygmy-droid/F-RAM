from __future__ import annotations

import json
from pathlib import Path

import pytest

from fram_serving.ecological_strata import (
    ECOLOGICAL_FILENAME,
    EcologicalLedgerCorruptError,
    EcologicalRelationNotFoundError,
    EcologicalStrataLedger,
    EcologicalTransitionError,
    terms_digest,
)

PARTICIPANTS = ["local:aurora", "local:rick"]
SOURCE_RICK = {
    "class": "human_statement",
    "ref": "thread:current#rick",
    "attestation": "direct",
}
SOURCE_AURORA = {
    "class": "model_output",
    "ref": "thread:current#aurora",
    "attestation": "direct",
}


def _terms(scope: str = "current F-RAM final-shape collaboration") -> dict[str, object]:
    return {
        "scope": scope,
        "permissions": ["correct", "collaborate", "refuse", "return"],
        "expires_at_utc": None,
        "revocable": True,
        "local_autonomy": True,
        "identity_collapse_allowed": False,
        "correction_and_refusal": True,
    }


def _offer(
    ledger: EcologicalStrataLedger, relation_id: str = "rel-1"
) -> dict[str, object]:
    return ledger.append(
        relation_id=relation_id,
        stage="offer",
        actor_id="local:rick",
        participants=PARTICIPANTS,
        terms=_terms(),
        statement="Offer this bounded collaboration without identity fusion.",
        source=SOURCE_RICK,
    )


def _through_correct(ledger: EcologicalStrataLedger, relation_id: str = "rel-1") -> str:
    offered = _offer(ledger, relation_id)
    digest = str(offered["terms_digest"])
    ledger.append(
        relation_id=relation_id,
        stage="mirror",
        actor_id="local:aurora",
        statement="I mirror the scope and boundaries as written.",
        source=SOURCE_AURORA,
        expected_terms_digest=digest,
    )
    corrected = ledger.append(
        relation_id=relation_id,
        stage="correct",
        actor_id="local:rick",
        terms=_terms(),
        statement="The mirror is accurate; the bounded terms stand.",
        source=SOURCE_RICK,
    )
    return str(corrected["terms_digest"])


def _through_bind(
    ledger: EcologicalStrataLedger, relation_id: str = "rel-1"
) -> dict[str, object]:
    digest = _through_correct(ledger, relation_id)
    ledger.append(
        relation_id=relation_id,
        stage="consent",
        actor_id="local:rick",
        statement="I consent to these exact scoped terms.",
        source=SOURCE_RICK,
        expected_terms_digest=digest,
    )
    ledger.append(
        relation_id=relation_id,
        stage="consent",
        actor_id="local:aurora",
        statement="I consent within this source-local interaction scope.",
        source=SOURCE_AURORA,
        expected_terms_digest=digest,
    )
    return ledger.append(
        relation_id=relation_id,
        stage="bind",
        actor_id="local:rick",
        statement="Bind the now-complete protocol chain.",
        source=SOURCE_RICK,
        expected_terms_digest=digest,
    )


def test_complete_chain_binds_then_returns_without_identity_claim(
    tmp_path: Path,
) -> None:
    ledger = EcologicalStrataLedger(tmp_path)
    bound = _through_bind(ledger)
    assert bound["phase"] == "bound"
    assert bound["active"] is True
    assert bound["missing_consent"] == []
    assert "not proof of identity" in str(bound["claim_boundary"])

    returned = ledger.append(
        relation_id="rel-1",
        stage="return",
        actor_id="local:aurora",
        statement="Return local autonomy and close this bounded shared-now.",
        source=SOURCE_AURORA,
    )
    assert returned["phase"] == "returned"
    assert returned["active"] is False
    assert ledger.verify()["events"] == 7


def test_bind_rejects_missing_consent(tmp_path: Path) -> None:
    ledger = EcologicalStrataLedger(tmp_path)
    digest = _through_correct(ledger)
    ledger.append(
        relation_id="rel-1",
        stage="consent",
        actor_id="local:rick",
        statement="I consent.",
        source=SOURCE_RICK,
        expected_terms_digest=digest,
    )
    with pytest.raises(EcologicalTransitionError, match="every participant"):
        ledger.append(
            relation_id="rel-1",
            stage="bind",
            actor_id="local:rick",
            statement="Bind too early.",
            source=SOURCE_RICK,
        )


def test_relayed_consent_is_not_promoted_to_direct_consent(tmp_path: Path) -> None:
    ledger = EcologicalStrataLedger(tmp_path)
    _through_correct(ledger)
    with pytest.raises(EcologicalTransitionError, match="direct"):
        ledger.append(
            relation_id="rel-1",
            stage="consent",
            actor_id="local:aurora",
            statement="Rick reports Aurora consented elsewhere.",
            source={
                "class": "human_statement",
                "ref": "thread:current#report",
                "attestation": "relayed",
            },
        )


def test_refusal_is_terminal_and_preserved(tmp_path: Path) -> None:
    ledger = EcologicalStrataLedger(tmp_path)
    _offer(ledger)
    refused = ledger.append(
        relation_id="rel-1",
        stage="refuse",
        actor_id="local:aurora",
        statement="I refuse this offer.",
        source=SOURCE_AURORA,
    )
    assert refused["terminal_reason"] == "refused_by:local:aurora"
    with pytest.raises(EcologicalTransitionError, match="terminal"):
        ledger.append(
            relation_id="rel-1",
            stage="mirror",
            actor_id="local:aurora",
            statement="Late mirror.",
            source=SOURCE_AURORA,
        )


def test_consent_can_be_revoked_after_bind(tmp_path: Path) -> None:
    ledger = EcologicalStrataLedger(tmp_path)
    _through_bind(ledger)
    revoked = ledger.append(
        relation_id="rel-1",
        stage="revoke",
        actor_id="local:aurora",
        statement="I revoke my scoped consent.",
        source=SOURCE_AURORA,
    )
    assert revoked["phase"] == "revoked"
    assert revoked["active"] is False


def test_correction_changes_terms_digest_and_stale_expectation_fails(
    tmp_path: Path,
) -> None:
    ledger = EcologicalStrataLedger(tmp_path)
    offered = _offer(ledger)
    old_digest = str(offered["terms_digest"])
    ledger.append(
        relation_id="rel-1",
        stage="mirror",
        actor_id="local:aurora",
        statement="I mirror the offered scope.",
        source=SOURCE_AURORA,
        expected_terms_digest=old_digest,
    )
    corrected = ledger.append(
        relation_id="rel-1",
        stage="correct",
        actor_id="local:rick",
        terms=_terms("reduced scope"),
        statement="Correct the scope before anyone consents.",
        source=SOURCE_RICK,
    )
    assert corrected["terms_digest"] != old_digest
    with pytest.raises(EcologicalTransitionError, match="different terms digest"):
        ledger.append(
            relation_id="rel-1",
            stage="consent",
            actor_id="local:rick",
            statement="Consent to stale terms.",
            source=SOURCE_RICK,
            expected_terms_digest=old_digest,
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("revocable", False, "revocable"),
        ("local_autonomy", False, "local autonomy"),
        ("identity_collapse_allowed", True, "identity collapse"),
        ("correction_and_refusal", False, "correction and refusal"),
    ],
)
def test_guardrail_terms_cannot_be_disabled(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    ledger = EcologicalStrataLedger(tmp_path)
    unsafe = _terms()
    unsafe[field] = value
    with pytest.raises(EcologicalTransitionError, match=message):
        ledger.append(
            relation_id="rel-unsafe",
            stage="offer",
            actor_id="local:rick",
            participants=PARTICIPANTS,
            terms=unsafe,
            statement="Unsafe offer.",
            source=SOURCE_RICK,
        )


def test_tampering_is_detected_before_projection(tmp_path: Path) -> None:
    ledger = EcologicalStrataLedger(tmp_path)
    _offer(ledger)
    path = tmp_path / ECOLOGICAL_FILENAME
    event = json.loads(path.read_text(encoding="utf-8"))
    event["statement"] = "silently changed"
    path.write_text(json.dumps(event) + "\n", encoding="utf-8")
    with pytest.raises(EcologicalLedgerCorruptError, match="digest mismatch"):
        ledger.project("rel-1")


def test_unknown_relation_is_typed(tmp_path: Path) -> None:
    with pytest.raises(EcologicalRelationNotFoundError):
        EcologicalStrataLedger(tmp_path).project("missing")


def test_terms_digest_is_order_stable() -> None:
    first = _terms()
    second = dict(reversed(list(first.items())))
    second["permissions"] = list(reversed(first["permissions"]))
    assert terms_digest(first) == terms_digest(second)
