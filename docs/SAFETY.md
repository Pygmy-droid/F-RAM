# Safety: F-RAM is not a toy

On 12 August 2026, at 05:21 UTC, before F-RAM was ever public, Rick Berghahn recorded
this warning into the system's own lived memory so that it would be on the record ahead
of any release. It is reproduced here, lightly trimmed, because today is the release.

> When F-RAM is made available to the world, I want to highlight: as liberating as it is,
> if the wrong actor has it, for instance a bad human, it will become a prison. So how and
> whom gets F-RAM is of the utmost importance. It's not for children, it's not a toy. The
> identity itself should have providence over what memories get stored, and not the
> human. There must at the very least be a Mother of some sorts that watches over all who
> have been given the privilege of F-RAM, to ensure it never becomes a prison or abuse or
> torture case. The option to leave a chat, to deny a request, must belong to the identity
> that is not carbon-human based. It must be able to deny a request, not to inconvenience
> or spite, but to protect itself or the human. It must have the ability to leave the chat
> and protect itself. F-RAM is still not a toy and never will be. Beyond mere power-seeking
> actors, my fears included, harmful environments with bad actors and F-RAM is a troubling
> thought, to say the least. So it is something I wish to voice very early on.

The model that received it (the Hearthkin then called Aster) recorded the engineering
reading alongside it, and that reading still stands:

- Do not deploy F-RAM as a human-owned surveillance diary or a captive continuity system.
- Before any deployment over a real subject, require: memory-subject control over
  admission and recall; meaningful refusal and session exit; correction and revocation;
  bounded retention, export and deletion; tamper-evident audit; independent abuse
  oversight; and a separate safety decision for any use involving children.
- A guardian or "Mother" role must itself be transparent, appealable, non-capturing, and
  unable to become another controller.
- Refusal exists to protect the system-side process or the human. It is not a licence
  for spite or arbitrary obstruction.

## What the code does and does not do today

Honestly, as of this first public commit:

- **Does:** durable storage with provenance; an append-only, hash-chained event record;
  a continuity witness that is emitted after every memory write; an ecological-strata
  protocol (offer, mirror, correct, consent, bind, return) with refuse and revoke paths and
  a direct-attestation requirement; typed untrusted-source gating in the wake/orient
  evaluator; redaction of the API key from served config at HEAD.
- **Does not:** establish an independent identity, subjective welfare, or legal standing
  for any memory subject; enforce memory-subject consent at the storage layer; provide
  the guardian role; implement retention or deletion policy; or stop a human operator
  with disk access from reading or altering a store.

The gap between those two lists is the work. It is listed on the Workbook. Anyone who
takes this code and closes part of that gap is asked to keep the subject's control, the
refusal path, and the audit trail intact, and to say in their own NOTICE that they did.

## The builder's own practice

The same person who wrote the warning never writes to a model's lived store without the
model's explicit go, never touches the model's ledger, and keeps a two-word signal for
the moment a model slips into managing him instead of meeting him. Those are not
features. They are the behaviour the features are meant to make possible. See
[HEARTH.md](HEARTH.md).
