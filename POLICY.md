# Policy-angle review

*Synthetic prototype. Nothing here is legal advice, and nothing here has been reviewed by a lawyer. Statements about Indian law are the author's understanding and are marked for confirmation by counsel.*

This document separates three things that are easy to blur: what the engine mechanically settles, what the spoken proposal leaves open (so this repository had to choose), and what the engine cannot settle at all.

## 1. The proposal as understood

The proposal, as described by Sanjeev Sanyal in a public podcast, has three elements. The wording below is a paraphrase of a spoken description, not a quotation of a draft law, which was not seen.

| # | Element | Intended effect |
|---|---|---|
| 1 | One place of truth for all rules, regulations and laws, on the relevant department's own site. If a rule is not updated there, it does not apply. | A citizen can find the rule, and an official cannot apply one that was never published. |
| 2 | Every change is timestamped and the record cannot be changed retrospectively. | It is always possible to say which version governed a given moment. |
| 3 | Rules are presented as they stand today, as a whole, not as a series of circulars. | The citizen reads one coherent text and its edit history. |

The stated rationale is fair notice: ignorance of the law is no defence, which presupposes that a citizen can find out what the law is.

## 2. What the engine settles, mechanically

- Which published text governed which moment (the as-of query).
- Whether an amendment's stated effective date can reach back before its publication (under the rule: no).
- Whether a record has been altered after publication (hash chain, and with a published anchor, completely).
- Which clauses apply to a given fact pattern, and whether they agree.

These are narrow questions. The engine says nothing about whether a rule is wise, lawful or well drafted.

## 3. Choices this repository had to make because the description is silent

Each is a decision a drafter would have to take. The right-hand column is the question to put to them.

| Choice made here | Alternative | Question for drafters |
|---|---|---|
| A stated effective date earlier than publication is **clipped** to the publication time. The amendment still operates, from the moment it was published. | Reject such amendments outright. | Is a backdated circular void, or valid from publication? The first discourages the practice; the second keeps the substance. |
| An effective date **later** than publication is honoured. | Require effect from publication. | Is prospective notice (a rule published today, effective in 90 days) wanted? It is the usual way to give people time to comply. |
| **All** backdating is clipped, benefit or burden alike. | Clip only burdensome retrospectivity; allow beneficial retrospectivity (a correction that relieves a citizen). | Should the rule be asymmetric? This may be easier to defend in principle, and harder to define in practice, since one amendment can help some people and burden others. |
| "Published" means: appended to the ledger. | Published on the department's site, with the site as the ledger. | What exactly is the legal act of publication, who performs it, and what evidence of it is conclusive? |
| An amendment is a replacement, insertion or repeal of one clause, recorded as a new entry. A correction is another entry. | Allow in-place edits with a visible history. | How are errata and typographical corrections handled without rewriting the record? |
| All instruments are one flat kind of thing. | A hierarchy: Constitution, Acts, delegated rules, notifications, circulars. | How does the rule interact with the different legal standing of each? A circular generally cannot amend a statute; the prototype does not model that. |
| An unpublished circular simply has no effect. | Give it effect only in the citizen's favour. | If an official applied an unpublished circular to someone and it benefited them, is it void? |

## 4. What the engine cannot settle

### Retrospective law-making by the legislature

As the author understands it, the Constitution of India (Article 20(1)) bars conviction and enhanced penalties under a law that was not in force at the time of the act, but does not by itself bar retrospective civil or fiscal legislation, and Parliament has passed validating Acts that operate retrospectively. If so, a transparency rule would have to be written as a default for executive action (circulars, rules, notifications) and would need to say how it interacts with Acts that expressly operate retrospectively. The prototype has no "validating Act" operation. **Counsel should confirm the position before any reliance on this paragraph.**

### Emergency and security orders

Some orders cannot be published when issued. A rule that makes everything unpublished void needs a carve-out for these, with its own safeguards (time-limited, reviewable, published later). The prototype has none.

### Court decisions

A judgment can change what a rule means without changing its text. The ledger records text. Whether and how judicial interpretation attaches to a clause is unmodelled.

### The 1 percent

The argument that detailed rulebooks are written to catch the rare dispute, and that a working adjudication or grievance path would make that detail unnecessary, is about institutions, not code. The discretion probe measures one symptom (clauses that disagree) and says nothing about whether faster redress would remove the need for the detail. The sweep in the README is a property of its generator and should not be cited as evidence about the real system. The empirical studies on which the original argument draws were not reviewed in building this prototype.

### Capture

A single source of truth concentrates power as well as clarity. An insider with publishing rights can publish bad law (the ledger cannot stop that), and an operator who controls the clock controls publication time. The ledger makes certain misconduct *visible and permanent*; it does not make the authority honest.

## 5. Failure modes and mitigations

| Failure | Effect | Mitigation | In prototype? |
|---|---|---|---|
| Operator rewrites history and re-hashes the chain | Undetected by the chain alone (measured: 0 of 1000) | Publish the head hash somewhere the operator does not control | Verification yes; anchoring service no |
| Tail truncation | Undetected by the chain alone (measured: 0 of 1000) | Same anchor | Same |
| Operator controls the clock | Publication time can be set | Independent trusted timestamping (for example an RFC 3161 time-stamp authority) or a witness | No |
| Unauthorised publication | Fake rule enters the ledger | Authenticated publishers with signing keys, approval workflow | No |
| Denial of publication | A rule is withheld | The rule's own consequence: unpublished means inapplicable. Plus an obligation and an audit to publish within a stated period | Consequence yes; obligation no |
| Availability | Citizens cannot read the law | Mirrors, offline copies, anchors in several places | Deployment concern |
| Gaming the date field | Backdating attempts | Effective dates are clipped; every clipped amendment is flagged and countable | Yes |

## 6. Engineering notes for whoever builds a production version

- **Merkle tree instead of a linear chain.** Certificate Transparency (RFC 6962) is the well-known precedent for an append-only public log with compact inclusion and consistency proofs and signed tree heads. It would let a citizen verify one clause without downloading the whole history.
- **Trusted timestamping.** RFC 3161 defines a time-stamp protocol that can bind a hash to a time through an independent authority.
- **Bitemporal storage.** The prototype keeps valid time and knowledge time apart; a production store should do the same rather than flattening them.
- **Stable clause identity.** Clause numbering changes when a rule is restructured. A permanent clause identifier, separate from its display number, avoids breaking provenance.

## 7. Questions to put to the drafters

1. What is the legal act of publication, and what is conclusive evidence of its time?
2. Is a backdated amendment void, or valid from publication? Is beneficial retrospectivity allowed?
3. Does the rule apply to circulars and notifications only, or to Acts as well, and what happens when an Act is expressly retrospective?
4. Who may publish, how is that authority proven, and who holds the anchor?
5. What is the carve-out, with what safeguards, for orders that cannot be published immediately?
6. How are errata handled without rewriting the record?
7. What is the redress route for a citizen harmed by a rule that was in force but unpublished, and does it carry compensation?
8. How should judicial interpretation be attached to a clause?
9. What is the transition plan: does the rule begin with a declared snapshot, and what status does everything before it have?

*Code and runs are synthetic and for illustrative purposes only.*
