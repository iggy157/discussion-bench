# Analysis — talk (exemplar, from situations)

Based on the provided exemplars and the structural requirements of the AIWolf system, here are my observations regarding the causal mapping of game states to discussion dynamics.

### 1. Board Situation $\rightarrow$ Agenda Mapping
The primary driver of the agenda is the distribution of "knowns" versus "unknowns." The tone shifts from exploratory to accusatory based on the following triggers:

*   **Seer CO Distribution:**
    *   **1-CO:** The agenda focuses on *verification*. The group treats the CO as a provisional truth-teller and looks for contradictions in others' claims to validate them. The tone is generally cooperative.
    *   **2-CO+:** The agenda shifts to *conflict resolution*. The primary goal becomes identifying the "fake" Seer. The tempo accelerates as players are forced to pick sides or find logical flaws in the competing claims.
*   **The "Black" Result:**
    *   A "Black" (Werewolf) result creates a high-pressure focal point. The agenda narrows immediately to the accused. The tone becomes scrutinizing, and the tempo slows down to allow the accused to defend themselves before a rush to vote.
*   **Night-Attack Results:**
    *   **No one died:** Shifts the agenda toward analyzing the Werewolves' hesitation or the presence of a protective role (e.g., Knight).
    *   **A known "White" died:** Increases urgency and suspicion. The tone becomes more cautious, and the agenda shifts toward "who benefited most from this death?"
*   **Player Count & Role Distribution:**
    *   As the player count drops, the "cost of a mistake" increases. The agenda shifts from "finding any werewolf" to "ensuring we don't kill a villager." The tone becomes more conservative and analytical.

### 2. Discussion Patterns & Situational Triggers
*   **The "Cross-Examination" Pattern:** Arises when a player's current claim contradicts a statement made in a previous turn or day. This is used to expose Werewolves who have failed to maintain a consistent narrative.
*   **The "Devil's Advocate" Pattern:** Arises when the majority is converging too quickly on a single target. This is used by cautious Villagers to prevent a "lynch mob" mentality or by Werewolves to sow doubt and divert the vote.
*   **The "Synthesis" Pattern:** Arises just before the voting phase. A player aggregates the day's findings (e.g., "Seer says A is black, B is acting suspicious, C is silent") to create a logical hierarchy of targets.

### 3. Per-Day Phase Dynamics
*   **Day 0 (Orientation):** Low-stakes. Focus is on establishing a baseline of behavior, agreeing on how information will be shared, and gauging the "voice" of other players.
*   **Day 1 (The Reveal):** High-density information phase. The morning is dominated by Role Claims (COs) and Seer results. The mid-day is a Q&A session to test the validity of those claims. The end-day is the first critical vote.
*   **Day 2+ (The Iteration):** The focus shifts to *consistency*. The agenda is driven by the night's casualties and whether the remaining players' behaviors align with the roles they claimed on Day 1.

### 4. Turn Progression & Closing
*   **Turns 0–3 (Deliberation):** This is the space for hypothesis testing, questioning, and debating. The goal is to move the group toward a consensus or a shortlist of suspects.
*   **The Final Turn (Execution):** This is strictly for the vote declaration. To maintain game flow, the final utterance must be a clear `@mention` of the target. Deliberation must be concluded *before* this turn to avoid wasting the final opportunity to signal intent.

### 5. Spread of Responses (Avoiding Echo Chambers)
To maintain a realistic and strategic atmosphere, players must not all agree. The responses to a proposal should be distributed:
*   **Concise Agreement:** "I agree with that logic." (Fast-tracks the vote).
*   **Agreement with Caveat:** "I agree, but only if [Player X] can't explain their silence." (Adds a condition).
*   **Alternative Angle:** "That's possible, but what if the Seer is actually the werewolf?" (Introduces a new hypothesis).
*   **Neutral Observation:** "I noticed [Player Y] hasn't spoken since the result was announced." (Provides raw data without a conclusion).
*   **Skip/Pass:** Remaining silent to observe others' reactions.

### 6. Off-Mainstream Positioning (Handling Attack)
When a player becomes the target, they should avoid a simple "I am innocent" binary. The response depends on the situation:
*   **Admitting Fault (Tactical):** "I realize my phrasing was confusing, let me clarify..." (Used when a logical slip occurred).
*   **Neutral Observer:** "I see why you're suspicious, but let's look at the facts together." (De-escalates the emotion).
*   **The Refocusing Organizer:** "While you're focused on me, we're ignoring the fact that [Player Z] is acting very strange." (Deflects by pivoting to a higher-priority target).
*   **Holding Back:** Providing minimal information to see how the attackers coordinate their logic (often used by Werewolves to find the Seer).

### 7. Utterance Construction & Voice
The "Gold Standard" for a move is not a standalone statement, but a **linked chain of thought**:
1.  **Anchor:** Reference a specific point made by another player ("Regarding what [Player A] said about the Seer's result...").
2.  **Analysis:** Add a layer of judgment or a logical bridge ("...it seems inconsistent with the fact that [Player B] claimed to be the Knight...").
3.  **Conclusion:** Provide a short, actionable takeaway ("...therefore, I suspect one of them is lying").

This structure ensures the conversation feels like a cohesive dialogue rather than a series of disconnected monologues, while maintaining the character's specific persona throughout the game.
