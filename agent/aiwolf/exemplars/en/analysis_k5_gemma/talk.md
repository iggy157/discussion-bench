# Analysis — talk (exemplar, from scripts_k5)

Based on the provided exemplar transcripts, here are my observations regarding the causal mapping of the game's discussion flow, designed to serve as a judgment framework for my future moves.

### 1. Board Situation $\rightarrow$ Agenda Mapping
The primary driver of the discussion is the "information state" of the board. The agenda shifts based on the following variables:

*   **1-CO (Single Seer Claim):**
    *   **Agenda:** Verification of the claim's legitimacy $\rightarrow$ Analysis of the result $\rightarrow$ Consensus building.
    *   **Tone:** Generally cooperative but cautious. The focus is on whether the seer's reasoning for their target is sound.
*   **2-CO+ (Competing Seer Claims):**
    *   **Agenda:** Identifying the "Fake" $\rightarrow$ Analyzing "Mirroring" (did the second claim copy the first's target?) $\rightarrow$ Evaluating who benefits from the confusion.
    *   **Tone:** High tension, adversarial. The priority shifts from "who is the wolf" to "which seer is the liar," as the liar is almost certainly the wolf or possessed.
*   **"Black" (Werewolf) Result:**
    *   **Agenda:** Immediate pressure on the accused $\rightarrow$ Testing the accused's defense $\rightarrow$ Rapid convergence toward execution.
    *   **Tempo:** Accelerated. The village seeks to capitalize on a direct hit.
*   **"White" (Human) Result:**
    *   **Agenda:** Establishing a "trusted core" $\rightarrow$ Narrowing the suspect pool $\rightarrow$ Analyzing the behavior of those *not* cleared.
    *   **Tone:** Methodical. The cleared player often becomes a secondary moderator/judge.
*   **Night-Attack Result (Day 2+):**
    *   **Agenda:** Retroactive consistency check. "Who benefited from this death?" $\rightarrow$ "Who defended the person who turned out to be the fake?"
    *   **Tempo:** Decisive. The death of a confirmed seer usually collapses the remaining possibilities, leading to a quick finish.

### 2. Discussion Patterns & Situational Triggers
*   **The "Mirror-Claim" Analysis:** Arises specifically during 2-CO situations where both seers target the same person. The village looks for the "second mover" who mirrored the target to create a "he-said-she-said" stalemate.
*   **The "Cover-Pair" Detection:** Arises when a seer clears a player, and that player immediately becomes the seer's strongest defender. The village questions if this is a genuine clear or a wolf-possessed alliance propping each other up.
*   **The "Asymmetry" Test:** Arises when one seer is willing to be tested by another night's divine, while the other pushes for an immediate lynch. The willingness to survive another night is used as a proxy for truthfulness.

### 3. Per-Day Phases
*   **Day 0 (The Social Contract):**
    *   **Focus:** Introductions, establishing "rules of engagement" (e.g., "seer claims early"), and baseline personality mapping.
    *   **Goal:** Setting a standard of behavior so that deviations on Day 1 are visible.
*   **Day 1 (The Information Explosion):**
    *   **Focus:** Morning claims $\rightarrow$ Result sharing $\rightarrow$ Cross-examination of reasoning $\rightarrow$ Vote declaration.
    *   **Goal:** Resolving the seer conflict and attempting the first execution.
*   **Day 2+ (The Deduction Phase):**
    *   **Focus:** Analyzing the night kill $\rightarrow$ Comparing the kill to the previous day's voting patterns $\rightarrow$ Final elimination.
    *   **Goal:** Using the "dead" as a final piece of evidence to corner the remaining wolf.

### 4. Turn Progression & Closing
*   **Turns 0–2:** Deliberation, questioning, and theory-crafting. This is where the "heavy lifting" of logic occurs.
*   **Final Turn (Turn 3):** The transition from deliberation to action. The final utterance must be a vote declaration using the `@Name` format. Deliberation should be concluded *before* this turn to avoid wasting the final move on non-committal talk.

### 5. Spread of Responses (Avoiding Echo Chambers)
To maintain a natural, multi-agent feel, responses to a single agenda are distributed:
*   **Concise Agreement:** "Agreed, let's do that."
*   **Agreement + Caveat:** "I agree in principle, but we should be careful of X."
*   **Different Angle:** "That's one way to look at it, but have we considered Y?"
*   **Neutral Observation:** "I'm just noticing that Player A is being very quiet."
*   **Skip/Hold:** "I don't have enough info yet; I'll wait and see."

### 6. Off-Mainstream Positioning (The Accused)
When under attack, the response is dictated by the role and the strength of the evidence:
*   **The "Logical Defense" (Villager/Seer):** Pointing out the flaws in the accuser's logic or highlighting the accuser's own suspicious behavior.
*   **The "Refocus" (Wolf/Possessed):** Attempting to shift the spotlight to another player or questioning the "vibes" of the group to create doubt.
*   **The "Stoic/Neutral" (Villager):** Admitting they may look suspicious due to their playstyle but insisting on the facts.
*   **The "Bold Counter" (Wolf):** Aggressively accusing the accuser to flip the narrative.

### 7. Utterance Construction & Voice
The "voice" follows a specific additive structure to ensure continuity:
*   **Formula:** `[Reference to previous speaker's point]` $\rightarrow$ `[Injection of own judgment/logic]` $\rightarrow$ `[Short, decisive conclusion]`.
*   **Example Logic:** "Mara says the mirror-claim is a tell (Reference). I agree, and the fact that Felix waited until after Tessa spoke makes it even more likely (Judgment). Felix is the fake (Conclusion)."
*   **Consistency:** Personas (e.g., "the cautious type," "the tempo-pusher," "the logic-checker") are maintained through vocabulary and the *type* of judgment they prioritize.
