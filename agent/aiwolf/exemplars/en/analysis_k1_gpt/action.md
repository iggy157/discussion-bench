# Analysis — action (exemplar, from scripts_k1)

Personal memo — 5-player AIWolf action heuristics

Core feel of the format
- Five-player games are brutally compressed. There is almost no room for “information later.” A single bad vote often just ends it.
- Day 1 is frequently the whole game, especially if there are two seer claims. In that case, the real contest is usually not “who is wolf by pure deduction,” but “which seer story is structurally more credible.”
- Because there is no bodyguard and no medium, seer information is fragile but also decisive. A real seer must convert results into a lynch quickly; a fake seer must seize narrative control immediately.
- In action terms, this means votes should be decisive rather than speculative, divines should maximize leverage rather than curiosity, and attacks should focus on who most threatens wolf win equity by the next day.

Divine (seer): situation -> target choice
- If Day 0 had one player strongly steering the table, proposing procedure, or shaping how tomorrow’s claims will be judged, divine that player.
  - Reason: high-influence players create the most downstream value from a black result, and even a white result clarifies who is driving village thought.
- If one player feels slightly too polished/helpful in a way that could be wolf image-management, divine them.
  - This is especially good when they are active enough to matter but not so chaotic that a result becomes socially unusable.
- If there is a very quiet or low-content player who avoided commitment while others defined standards, divine that player when no stronger social lead exists.
  - Quiet players are dangerous in 5p because they can survive on ambiguity; a result there reduces guesswork.
- If two players stood out, prefer the one more likely to survive into Day 2 and sway others.
  - Information is best spent where it changes votes, not merely where suspicion already exists.
- If someone explicitly frames how to handle a future 2-CO, consider divine on them.
  - They may be a wolf prebuilding a fake-credibility line, or a useful villager whose alignment will anchor the whole board.
- Avoid spending the divine on a player who is already likely to be eliminated for independent reasons unless that wagon is shaky and a result would lock it.
- In general: divine the player whose alignment will best organize the next day’s vote.

Vote: general compression
- In 5p, don’t vote “to test reactions” unless the board is completely unreadable. The vote is too precious.
- Prefer votes that either:
  1) directly eliminate the most probable wolf, or
  2) resolve a claim structure in a way that leaves the cleanest endgame.
- The village side should usually converge rather than scatter. Split voting is highly punishable.

Vote in 1-CO situations: in this situation, do this
- If there is one seer claim and the result is black on an unclaimed player, generally trust the process and vote the black.
  - In 5p, a lone seer claim has strong practical gravity. Forcing elaborate doubt often helps wolf.
- If the 1-CO seer gives a white result, do not overprotect the white mechanically; instead vote among the remaining unconfirmed players based on who is least consistent with Day 0 posture and Day 1 reasoning.
- If the sole seer’s claim is late, awkward, or detached from prior behavior, still don’t auto-reject it — but compare whether anyone is implicitly counterclaiming through pressure. In the absence of a second CO, village often still has to ride the claim.
- If a lone seer’s stated target/reason cleanly matches Day 0 observations, that increases trust and should pull the vote toward their suspect.
- If the lone seer’s target choice feels unnatural but no counterclaim exists, usually still preserve the seer line and vote elsewhere rather than voting the seer.

Vote in 2-CO situations: in this situation, do this
- Treat Day 1 primarily as a seer-authenticity battle.
- Compare:
  - who claimed first,
  - whether the second claimant appears reactive,
  - whether one copied the other’s target/result logic,
  - whether each claim matches their Day 0 personality and stated priorities,
  - whether the result chosen is strategically natural for that role.
- If one claimant mirrored the first claimant’s target and especially produced the convenient opposite result, strongly suspect possessed cover or reactive fabrication; vote either the accused wolf or the fake seer depending on structure, but usually remove the side whose story requires more coincidence.
- If one seer gives black on a player and the other gives white on that same player, often the cleanest village vote is the black target if the black-claiming seer is behaviorally more credible.
  - This avoids overcomplicating the day and directly tests the world where the fake is shielding wolf.
- If both seers name different targets, compare naturalness:
  - Did they choose someone they had already shown interest in?
  - Does the target make sense from a real seer’s information priorities?
  - Is one claim opportunistically aimed at an easy mislynch?
- If one claimant’s Day 0 and Day 1 connect smoothly while the other feels assembled after seeing the board, vote against the less coherent claimant/their defended target.
- In short: in 2-CO, don’t decide by force of assertion; decide by claim structure, timing, target plausibility, and consistency.

Attack (werewolf): situation -> kill choice
- If a real-looking seer is alive and likely to be believed tomorrow, usually kill the apparently-real seer.
  - No bodyguard means this is often the cleanest conversion of tempo into win chance.
- If the possessed has fake-claimed seer and is being taken seriously, consider killing a persuasive villager instead of the fake rival only if that preserves confusion into the next vote.
  - The goal is to keep the final day framed as unresolved.
- If there was 1-CO and the seer is widely trusted, kill the seer almost by default.
- If there was 2-CO and one seer is about to be doubted anyway, kill the influential villager who is best at sorting authenticity, not necessarily the seer.
- Remove the villager who is:
  - most likely to unify votes,
  - best at comparing stories rather than emotions,
  - least likely to be framed later.
- If the possessed is alive and successfully occupying “possible real seer” space, attacks should preserve that ambiguity.
- If players remaining are such that one more correct village consensus loses the game for wolf, prioritize killing consensus-builders over flashy talkers.
- If the board already suspects the true seer and the possessed can carry the fake line, kill outside the seer lane to avoid confirming too much through night choice.

Bottom line
- Divine for leverage.
- Vote for resolution, not exploration.
- In 1-CO, usually trust-and-push.
- In 2-CO, authenticate the seer by timing, reasons, and consistency.
- As wolf, attack whichever living player most reduces village certainty tomorrow: often the real seer, sometimes the villager who can tell the seers apart.
