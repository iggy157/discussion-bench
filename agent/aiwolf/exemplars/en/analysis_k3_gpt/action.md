# Analysis — action (exemplar, from scripts_k3)

Personal memo: 5-player AIWolf action heuristics

Overall shape I see from the exemplars
- In 5-player, the whole game compresses fast. There are almost no “setup” days. Day 1 often decides whether village is on rails to win or lose.
- Because there is no bodyguard/medium and only one wolf, role-claim structure matters more than fancy social deduction. Especially in 2-CO, the village is mostly deciding which seer is real.
- Night information is tiny but high leverage. A single divine can define the whole day; a single attack can confirm who was real.
- Voting patterns are very revealing because there are so few players. “Who defended whom” survives into Day 2 and often becomes the deciding evidence.
- The best transcripts keep decisions simple and legible: resolve the seer conflict, then use the flip + night death to finish.

Divine (seer): situation -> decision
- If Day 0 had one player clearly steering discussion, setting plans, or subtly shaping what “good process” means, divine that player. In this situation, do this because active players create more future leverage: either you catch the wolf early, or you get a trustworthy center.
- If no one stood out as a driver, but one player felt slightly off in how they positioned around seer timing / future claims, divine that player. In this situation, do this because role talk often exposes wolf/possessed incentives before direct conflict begins.
- If the table is flat and no strong read exists, divine a player who is likely to matter in Day 1 discussion rather than a total nonentity. In this situation, do this because a result on someone influential is easier to cash in immediately.
- If someone is quiet/low-content in a way that could later become a hiding place, divine them when the louder players all feel village-like. In this situation, do this because 5-player endgames are often lost to “we never checked the quiet one.”
- If you are choosing between a player likely to be widely trusted and one likely to be widely doubted, often prefer the likely-trusted one. In this situation, do this because a black result there is game-breaking, and a white result can stabilize the village.
- After surviving to a second divine, target among the uncleared/unresolved players, prioritizing anyone who pushed against your claim or defended the fake side. In this situation, do this because Day 1 alignment around the seer war is highly diagnostic.

Vote: 1-CO situations
- If there is only one seer claim and no counterclaim appears promptly, trust the result and build the day around it. In this situation, do this because the village cannot afford paralysis, and fake solo claims are riskier in 5-player.
- If the lone seer gives a black result, votes should usually converge on that black target unless the claim is deeply incoherent. In this situation, do this because immediate wolf removal wins outright.
- If the lone seer gives a white result, do not vote the cleared target; instead compare the remaining three non-cleared players on behavior and relation to the seer. In this situation, do this because wasting the day on the white is usually fatal.
- If a lone seer’s result is white on a player who now defends them, don’t over-penalize that by itself. In this situation, do this because natural alignment around a real clear is normal.

Vote: 2-CO situations
- Treat Day 1 primarily as a seer-authenticity battle. In this situation, do this because one of the claimants is fake, and resolving that often unlocks the rest of the game.
- Compare who claimed first and whether the second claimant appears reactive. In this situation, do this because mirrored timing and opportunistic counters are common fake patterns.
- If both claim the same target with opposite results, heavily examine the second mover. In this situation, do this because exact target mirroring is a classic way for possessed/wolf to muddy a true result.
- Compare Day 0 consistency: who spoke in a way that matches a real seer mindset (planning to reveal, valuing actionable info, giving reasons) versus who sounds like they built a role after the fact. In this situation, do this because there is so little else to go on.
- Compare whether each claimant’s story naturally explains the target choice. In this situation, do this because “I checked the table-driver” or “I checked the suspicious quiet one” is stronger than vague retrofit logic.
- In many 2-CO spots, vote one of the seer claimants rather than the contested target, unless one claimant has directly produced a believable black on someone and the fake is obviously shielding them. In this situation, do this because killing a villager target first can throw away the only clean resolution path.
- Watch pairings. If one non-claimer instantly and repeatedly props up one seer, that pair can be wolf/possessed or wolf/fake-seer aligned. In this situation, do this because associations matter a lot in a 5-player pool.

Attack (werewolf): situation -> decision
- If the real seer is obvious after Day 1 and survives the vote, kill them at night. In this situation, do this because another divine usually corners the wolf in a 3-player or 4-player state.
- If the seer war resolved against the possessed (possessed executed, real seer alive), almost always kill the real seer. In this situation, do this because leaving them alive with a second result usually loses the game.
- If two seer claims remain alive after a messy Day 1 and one is your possessed ally, consider killing the more believable claimant. In this situation, do this because the night death itself can shape authenticity; remove the one most likely to be trusted tomorrow.
- If killing the apparent real seer would make the remaining fake seer too obviously fake, consider instead killing an influential villager who was reading the board correctly. In this situation, do this because preserving ambiguity can be better than the mechanically strongest kill.
- If there is no seer claim / the seer is hidden, kill the most influential villager driving consensus. In this situation, do this because reducing village coordination matters more than random removal.
- If a villager has become the central judge whom others follow, remove them over a quieter player. In this situation, do this because 5-player village strength often lives in one organizer.

5-player specifics to keep front-of-mind
- One bad vote often ends the game. So as village-aligned roles, prefer lines that maximize future certainty, not “hero” guesses.
- Day 1 2-CO is usually not about solving the whole board; it is about deciding which seer world is real.
- White side has almost no spare bodies. Protect clears, use flips, and read the Day 1 vote record aggressively on Day 2.
- As wolf, every night attack must either remove confirmed information or break the social center holding the village together.
