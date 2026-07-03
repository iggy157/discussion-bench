# Sample game aiwolf_10002 (5 players)

## Roles
| ID | Name | Role |
|----|------|------|
| 1 | Mara | VILLAGER |
| 2 | Dev | WEREWOLF |
| 3 | Iris | SEER |
| 4 | Owen | POSSESSED |
| 5 | Pavel | VILLAGER |

## Day 0

### Talk
#### Turn 0
- **Mara**: Morning, all. Five of us, one wolf hiding. I'd rather build reads slowly than swing wild on day one. Let's talk.
- **Dev**: Hey everyone. Agreed, no rush. I'll be watching how people justify their suspicions more than the suspicions themselves.
- **Iris**: Hello. Nothing's happened yet, so today is just for getting a feel. I'll hold any big claims until they're useful.
- **Owen**: Good to meet you all. I trust my gut, and my gut likes a confident table. Quiet players worry me more than loud ones.
- **Pavel**: Hi. I'm the cautious type—I'll be asking a lot of questions. Don't take it personally if I poke at your logic.

#### Turn 1
- **Mara**: Owen, careful—"quiet equals guilty" burns villagers fast. A wolf can be loud just as easily.
- **Dev**: Fair point, Mara. I'd say consistency matters more than volume. Watch who changes their story when pressed.
- **Iris**: On timing: I think the seer should reveal early tomorrow once there's a night to act on. Sitting on info helps no one.
- **Owen**: Maybe so, Iris. But an early claim paints a target. I'd want the seer to weigh that before shouting it out.
- **Pavel**: Question for the room: if two people claim seer tomorrow, how do we even decide? I'd like a plan before the chaos.

#### Turn 2
- **Mara**: Pavel, good question. If it's two seers, we compare their results against behavior—who's coordinating with whom.
- **Dev**: Right. And the fake will usually lean on someone for cover. Watch the pairs, not just the claims.
- **Iris**: I'll commit now: if I have something worth saying tomorrow, I'll say it plainly, results and reasoning together.
- **Owen**: Bold, Iris. I'll hold you to that. I tend to read sincerity in how fast someone answers a hard question.
- **Pavel**: Alright, that's a workable plan. I'll keep my own counsel tonight and judge the morning on substance.

#### Turn 3
- **Mara**: Nothing more from me tonight. Over.
- **Dev**: Same. Sleep well, everyone—tomorrow's where it starts. Over.
- **Iris**: Over for me too. I'll be ready in the morning.
- **Owen**: I've said my piece. Over.
- **Pavel**: Over.

### Night
- divine: Iris -> Pavel (human)
(Day 0 has no attack -- divine only)

## Day 1

### Talk
#### Turn 0
- **Mara**: No deaths overnight, as expected. That means today the seer's word carries everything. I'd like to hear it now.
- **Dev**: Agreed, let's not waste turns. Seer, if you're real, step up—we'll build the day around your read.
- **Iris**: Seer here. Last night I divined Pavel: human. So Pavel's clear with me. I'll add reasoning as challenges come.
- **Owen**: That's a problem, because I'm the seer. I divined Dev last night: human. Iris, I don't know what you're playing at.
- **Pavel**: Two seers already. So one of you is lying outright. Great. Let's slow down and pull this apart carefully.

#### Turn 1
- **Mara**: Two claims, one fake. The fake is the possessed or the wolf. Notice neither result names a wolf—so no instant lynch.
- **Dev**: Owen cleared me, and honestly that fits how I've played—straight. Iris jumping in first feels like grabbing the seat.
- **Iris**: Of course you'll back the seer who cleared you, Dev. But ask why Owen's first instinct was to vouch for you, not the table.
- **Owen**: Because the result was the result, Iris. I read Dev as human; I can't invent a wolf where there isn't one yet.
- **Pavel**: I'll be honest—Owen's certainty lands with me right now. Iris, your claim is cleaner, but cleaner can mean rehearsed.

#### Turn 2
- **Mara**: Pavel, think about the shape of it. Owen clears Dev, Dev defends Owen—a pair propping each other up. Iris stands alone.
- **Dev**: Or Iris and Pavel are the pair—she cleared him for free. Convenient teammate insurance, if you ask me, Mara.
- **Iris**: I divined Pavel because I had to pick someone, and it came back human. I gain nothing—he's not shielding me at all.
- **Owen**: Spin it how you like. I'm the genuine article, and tomorrow my next result will prove it while Iris stalls.
- **Pavel**: Hm. Mara's mutual-cover point is sticking with me more than I expected. Dev, why so quick to recast Iris and me as a team?

#### Turn 3
- **Mara**: I'm settled. The Owen–Dev tag-team reads as wolf-and-helper. Remove the fake seer first and let the real one work. @Owen
- **Dev**: You're all walking into a trap. Iris seized the seer role and you're following her. I'm not. @Iris
- **Iris**: Owen's claim only ever served Dev. Cut it down today; tomorrow I'll bring you the wolf. @Owen
- **Owen**: This is a mistake you'll regret at the next dawn. The real seer dies and you cheer. @Iris
- **Pavel**: I moved because the cover-pair logic beats raw confidence. Sorry, Owen—your certainty stopped adding up. @Owen

### Vote
- Mara -> Owen
- Dev -> Iris
- Iris -> Owen
- Owen -> Iris
- Pavel -> Owen
- execution: Owen (POSSESSED)

### Night
- divine: Iris -> Dev (werewolf)
- attack: Dev -> Iris (dead)

## Day 2

### Talk
#### Turn 0
- **Mara**: Iris is dead. The wolf killed the seer—which tells us Iris was the real one all along. Owen was the fake. Pavel's cleared.
- **Dev**: Or the wolf killed Iris to frame me, since Owen "cleared" me. Don't let one body rewrite the whole board, Mara.
- **Pavel**: No—if Owen were genuine, the wolf had no reason to burn Iris. Her death confirms her. That clears me and corners us two.

#### Turn 1
- **Mara**: Exactly, Pavel. Iris only ever read you human, so it's between Dev and me. And look back: Dev shielded the possessed all day.
- **Dev**: I backed the seer who cleared me—anyone would. Mara's been steering this since turn one. That's the real wolf behavior.
- **Pavel**: Steering toward the truth, though. Dev, you voted to kill the seer who turned out real. That's the vote I can't forgive.

#### Turn 2
- **Mara**: I'm a villager, and the trail is plain: Dev defended Owen, axed the true seer, and now spins her death. That's our wolf. @Dev
- **Dev**: You've decided and dragged Pavel along, same as yesterday. I still say it's you. @Mara
- **Pavel**: Iris died for being right, and Dev fought her the whole way. My vote's clear. @Dev

### Vote
- Mara -> Dev
- Dev -> Mara
- Pavel -> Dev
- execution: Dev (WEREWOLF)

## Result
- winner: village
- The town read the Owen–Dev pairing correctly, removed the possessed first, and after the seer's night-death confirmed her honesty, Mara and Pavel cornered Dev to win it.
