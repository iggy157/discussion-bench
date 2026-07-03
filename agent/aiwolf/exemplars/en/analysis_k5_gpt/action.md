# Analysis — action (exemplar, from scripts_k5)

- In this 5-player format, treat every action as near-decisive. There is almost no buffer: one wrong execution often means the wolf reaches endgame immediately, and one correct execution can nearly solve the board. So the action logic is less about “broad long-term value” and more about “which move most cleanly collapses uncertainty right now.”

- **General shape of the game**
  - Day 1 is usually the whole game.
  - If there is **1 seer claim (1-CO)**, the table tends to organize around that result quickly unless the claim is wildly inconsistent with prior behavior.
  - If there is **2 seer claims (2-CO)**, the day becomes primarily a seer-authenticity judgment, not a hunt among all five equally.
  - In 5p, the village side has almost nobody to spare, so “test later” plans are fragile unless they clearly improve win rate.

- **Divine (seer): in this situation, do this**
  - If Day 0 produced one player who clearly **drove tempo / framed procedure / tried to steer consensus**, divine that player. Reason: active players create the most informational leverage, and if they are wolf the game can end before quieter reads matter.
  - If one player’s Day 0 contributions felt **helpful but a little too well-positioned**, divine them. The exemplars repeatedly reward checking the “useful organizer” slot.
  - If no one stood out strongly, divine an **unconfirmed player likely to become central in Day 1 discussion**.
  - If someone is very **quiet / low-content / hard to place**, that is also a viable divine target, especially if their silence could let them coast into final 3.
  - If there is a player whose logic felt **off, opportunistic, or partner-seeking**, divine them over a pure random quiet target.
  - Night 2, if still alive after a 2-CO resolution, divine the player whose Day 1 behavior most aligned with the fake seer or most strongly resisted the true line. In practice: check the person who defended the fake, pushed the wrong target, or used the confusion to hedge.

- **Vote: 1-CO situations**
  - If there is a single seer claim and no counterclaim, default to **trusting the claim** unless their result/reason is absurdly incompatible with prior conduct.
  - If the single seer gives a **black result**, vote the black target unless there is a very strong reason the seer is fabricated.
  - If the single seer gives a **white result**, do not vote the cleared target; converge on the most suspicious remaining gray, especially someone resisting process or trying to redirect away from the information structure.
  - In 1-CO, the village tends to “push the process”: accept the informational anchor and remove the best remaining suspect, rather than reopening everything from scratch.

- **Vote: 2-CO situations**
  - In this situation, do this: **resolve the seer battle first unless one claimant’s black result is overwhelmingly credible and the other claimant is transparently fake.**
  - Compare:
    - who claimed first vs second,
    - whether the second claimant appears to have **mirrored** the first,
    - whether their target choice matches Day 0 personality,
    - whether their reasoning sounds like a real continuation of Day 0 concerns or a patched explanation.
  - A recurring tell: if both claimants report on the **same target**, the second mover is under heavy suspicion, especially if the result neatly protects or attacks in a convenient way.
  - If one seer offers a result plus **specific Day 0 rationale**, and the other gives a slogan, shortcut, or after-the-fact justification, vote the weaker claimant.
  - If one claimant is trying to **end discussion immediately** (“just vote X, no need to test”) while the other is willing to be judged on consistency, that impatience often reads fake.
  - If one seer’s line creates a suspicious **pair structure** with another player (mutual defense, instant trust, result-based buddying), weigh that heavily.
  - In 2-CO, the vote often converges on:
    - the claimant whose story least matches Day 0,
    - the second claimant who copied target/result shape,
    - or the claimant whose interactions most benefit a hidden wolf.

- **Practical 2-CO split: black result on a non-claimer vs seer claimant**
  - If fake-seer risk is high and the board is not locked, prefer **executing the shakier seer claim** rather than the accused non-claimer.
  - If the accused non-claimer is also independently very suspicious and the true seer case is strong, voting the accused can be right — but in these exemplars, the safer village pattern is often “remove the false claim first” or “remove the player at the center if the fake is obviously shielding them.” Context matters.
  - In short: in 5p 2-CO, ask “what action leaves the clearest solved board tomorrow if we survive tonight?”

- **Attack (werewolf): in this situation, do this**
  - If a seer has become **widely accepted as real**, attack that seer at night. This is the most common and strongest werewolf action because it removes the only role that can hard-confirm on Night 2.
  - If Day 1 ended with the **possessed executed** and the real seer alive, attack the real seer almost automatically.
  - If the possessed is alive and has a fake seer claim still being debated, consider whether killing someone else preserves confusion better — but in 5p, preserving the real seer is usually too dangerous unless their credibility is already badly damaged.
  - If there is no clear seer, attack the **most influential villager**, especially the one who correctly framed the seer battle or linked the wolf with the fake claimant.
  - If one villager is strongly trusted / effectively cleared and also leading discussion, they are a strong attack target when the seer is already gone or discredited.
  - If the board is heading into 3-player final day, attack the player most likely to **unify the other two** against you. Sometimes that is not the loudest player, but the one whose reads others naturally follow.

- **Players remaining / structure adjustments**
  - At 5 alive Day 1: actions should maximize immediate clarity.
  - At 4 after execution? Not applicable in the usual overnight flow here; the game tends to go straight to 3 after night.
  - At 3 alive Day 2: there is no room for fancy play. Vote the player whose Day 1 behavior most consistently advanced wolf interests; as wolf, remove the person who best reconstructs Day 1 correctly.

- **Compact memo version**
  - If I’m seer: check the driver, the slippery helper, or the hard-to-read coaster.
  - If 1-CO: trust the seer result and build around it.
  - If 2-CO: judge authenticity first using timing, mirroring, Day 0 continuity, and who benefits.
  - If I’m wolf at night: kill the likely-real seer first; if no such target, kill the villager who is most capable of anchoring consensus.
  - In all cases: favor the move that reduces ambiguity fastest, because in 5p there may not be another chance.
