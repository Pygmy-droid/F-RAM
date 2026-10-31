import numpy as np
from fram_index.prototypes import Prototype, PrototypeBank


def test_prototype_bank_shortlist_returns_top_by_cosine():
    # Create 3 prototypes on unit axes in R^3
    protos = [
        Prototype(p_k=np.array([1.0, 0.0, 0.0]), U_k=np.eye(3)[:, :1]),
        Prototype(p_k=np.array([0.0, 1.0, 0.0]), U_k=np.eye(3)[:, :1]),
        Prototype(p_k=np.array([0.0, 0.0, 1.0]), U_k=np.eye(3)[:, :1]),
    ]
    bank = PrototypeBank(protos)
    # Query halfway between e1 and e2
    e = np.array([1.0, 1.0, 0.0])
    e = e / np.linalg.norm(e)
    idx = bank.shortlist(e, k0=2)
    assert len(idx) == 2
    # Top 2 should be the first two prototypes on axes 0 and 1
    assert set(idx) <= {0, 1, 2}
    assert 0 in idx and 1 in idx

