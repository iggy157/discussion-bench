# Analysis (exemplar, HB, from scripts_k1)

Personal memo on good HiddenBench discussion dynamics

The exemplar is a very clean case of how to turn individually misleading partial clues into a collectively correct answer. My main takeaway is that the value of an utterance depends heavily on phase: early turns should surface private constraints, middle turns should integrate and test, late turns should compress the joint reasoning into a consensus. The best utterances are not generic agreement; they add a new constraint, reconcile two constraints, or stress-test a candidate.

1. Surfacing: when and how to reveal private info

- Early discussion should put the private fragment on the table fairly directly. In the exemplar, the strongest progress came from agents stating their hidden clues with enough specificity to be operational:
  - “guilty person was driving a car”
  - “under thirty”
  - “man, father indirectly responsible, 110 km/h”
- This is the right granularity: enough detail to constrain hypotheses, but not bloated paraphrase. The point is to make your clue usable by others immediately.
- Withholding too long is harmful because other agents may keep reasoning from shared facts only, reinforcing wrong first impressions. In the exemplar, two agents initially fixated on the drunk father and one on the speeding motorcyclist; only explicit hidden facts broke those anchors.
- But disclosing “too early” in the wrong way can also be harmful if it is overinterpreted rather than stated neutrally. Example: “the drunk father must be guilty” is not useful; “my note says the car owner had 1.5 alcohol and the guilty person was inattentive” is useful. Surface facts, not just your current conclusion.
- Good early utterance template:
  - exact or near-exact hidden fact,
  - any important wording distinctions,
  - minimal interpretation.
- Especially valuable are hard constraints: gender, age, vehicle type, relation, role distinctions (“owner” vs “driver”), exact wording like “indirectly responsible.” These often eliminate candidates quickly.

2. Integration: how to combine fragments into a whole

- The middle game is where strong discussions separate themselves. Once fragments are out, utterances should start doing explicit combination work.
- Good integration moves in the exemplar:
  - “car” rules out the motorcycle suspect.
  - “under thirty” rules out the 53-year-old father.
  - “man” then rules out Mrs. Y, leaving the son.
- This is very effective because it turns separate clues into eliminations. Elimination-based integration is often safer than positive storytelling.
- Another strong integration move is role clarification. A key turning point was noticing that “owner tested at 1.5 alcohol” does not mean “owner was the guilty driver.” That distinction allowed Agent 1’s clue to harmonize with the others rather than conflict with them.
- So in my own turns, I should listen for apparently conflicting fragments and ask: can they both be true if they refer to different roles, times, or aspects?
- Good integration utterance formula:
  - cite one other agent’s fact,
  - connect it to your own or a prior established fact,
  - derive a narrowed candidate set or a role distinction.
- Example style: “If your clue says the culprit is in a car, then the 110 km/h can’t belong to the motorcyclist; combined with my ‘under thirty’ fact, that leaves only two car suspects.”

3. Verification: don’t accept a neat story without checking it

- The exemplar does not just race to the answer after the first apparent fit. It repeatedly asks whether the wording is exact and whether rival candidates still survive.
- Important verification behaviors:
  - ask if a constraint is verbatim or interpretive (“is ‘car’ exact wording?”)
  - test whether a clue truly excludes someone
  - make another agent walk through the rival candidate explicitly
  - revisit ambiguous terms like “owner,” “indirectly responsible,” “inexperienced”
- This matters because many HiddenBench tasks are designed so that premature synthesis can be wrong if a term was loosely paraphrased.
- Verification should be targeted, not skeptical for its own sake. In the exemplar, pushback was specific:
  - is “car” definitely not “vehicle”?
  - does Agent 2’s clue contradict the son?
  - can Mrs. Y still survive all the known facts?
- Good verification utterances often sound like:
  - “Does your wording literally say X?”
  - “Would candidate Y still fit all constraints?”
  - “I want to make sure we’re not collapsing owner and driver.”
- This style keeps the discussion evidence-led instead of momentum-led.

4. Avoiding premature convergence

- The biggest danger is everyone echoing the first plausible story. The exemplar avoids this by actively preserving live alternatives until they are excluded.
- Good signs:
  - agents openly revise initial votes
  - someone plays skeptic even when mostly convinced
  - they test Mrs. Y after the son already seems likely
  - they acknowledge where each initial hunch came from and why it failed
- This is important: a consensus is only trustworthy if all major alternatives have been checked against the full pooled evidence.
- In my own participation, if the group starts converging too fast, a useful utterance is not “I agree” but “Before we lock that in, does candidate B survive clue C?” That can either expose a gap or strengthen confidence if resolved.
- However, skepticism should not become wheel-spinning. Once every candidate but one is ruled out by explicit constraints, the right move is to summarize and align.

5. Phase-specific guidance

Early phase
- Priority: disclose your private fragment clearly.
- Avoid arguing for your pre-answer too strongly.
- Best contribution: one or two concrete facts with exact wording distinctions.
- If you have no special info, your role can be to prompt comparison: “let’s put all hidden notes side by side.”

Middle phase
- Priority: integrate clues and test conflicts.
- Best contribution: connect two pieces into an elimination or reconciliation.
- Ask exact-wording questions where ambiguity matters.
- Actively revisit your own initial interpretation if others’ facts undermine it.

Late phase
- Priority: compress the reasoning and ensure all candidates were considered.
- Best contribution: concise elimination chain or final consistency check.
- Help convert diffuse agreement into explicit consensus: “car eliminates Z, under-30 eliminates X, male eliminates Y.”
- Avoid repetitive “same here” unless the protocol needs explicit final alignment. Even then, add a short rationale if possible.

6. Utterance construction and anti-redundancy

- The most useful utterances are compact but progressive:
  - one fact from another agent,
  - one fact or distinction from you,
  - one conclusion.
- Example structure:
  - “Given your ‘under thirty’ clue, my ‘male’ clue rules out Mrs. Y, so only the son fits.”
- This avoids empty agreement and keeps each turn moving the state forward.
- Anti-patterns to avoid:
  - restating the current favorite without adding support
  - repeating the whole case every turn
  - defending your pre-answer after it has been ruled out
  - making broad intuitive claims when exact constraints are available
- If you’ve already given your fragment, later turns should shift from disclosure to one of:
  - clarification of wording,
  - reconciliation with another clue,
  - elimination of a remaining alternative,
  - final synthesis.

7. Meta-lesson

- HiddenBench rewards disciplined evidence pooling, not eloquence. The exemplar works because each agent contributes distinct information at the right time, updates when contradicted, and keeps discussion tied to exact constraints rather than vibe.
- My default aim should be: every turn must either add hidden information, sharpen interpretation, rule out a candidate, or close a verified gap. If my turn does none of those, it is probably redundant.

Bottom line:
- Early: state your clue plainly.
- Middle: connect clues and interrogate wording.
- Late: summarize the elimination logic and align.
- Always prefer exact constraints over intuitive stories, and prefer progress over repetition.
