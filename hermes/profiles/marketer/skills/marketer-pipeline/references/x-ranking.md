# X: For You ranking, review lenses and discovery

Knowledge for X content review, result analysis and conversation discovery.
It informs advice; it is not a posting formula, a score to optimize or a new
prohibition list, and it never authorizes an action on X.

## Source and expiry

Source: [xai-org/x-algorithm](https://github.com/xai-org/x-algorithm), commit
`b412112` (2026-10-03); X syncs production defaults into
`home-mixer/params/param.rs` by cron. Reviewed 2026-10-05. Production runs
experiments on parts of the traffic, so a default is not every viewer's value.
Grox prompts and some anti-abuse rules are unpublished. Recheck the README
"Notable Updates", `docs/` and `param.rs` when this note is older than three
months or a claim decides a recommendation; record the commit you read.

The 2023 `twitter/the-algorithm` weights (reply 13.5, reply engaged by author
75 and so on) describe a retired ranker. Never cite them as current.

## How For You selects a post

1. Candidates: recent posts of followed accounts (Thunder), out-of-network
   posts found by embedding similarity to the viewer's history (Phoenix
   retrieval, multimodal) and SimClusters.
2. Filters before scoring include: posts older than 48 hours; reposts and
   replies from accounts the viewer does not follow; already seen posts;
   muted keywords; blocked or muted authors; for new accounts, out-of-network
   posts below an engagement threshold.
3. Phoenix predicts, per viewer, the probability of each action. Final score
   = Σ weight × P(action).
4. Adjustments: author diversity (each further post of one author in the same
   feed request is multiplied by a decaying factor down to a floor); an
   out-of-network discount below 1, also applied to replies and reposts from
   followed accounts; a cold-start boost lifting a post toward roughly
   position 15 when its author has at most 50,000 followers, the post is at
   most 2 hours old and has fewer than 200 impressions.
5. Visibility filtering decides separately whether a post may be shown at all,
   from viewer actions and labels. The account owner can inspect labels on
   [Under the Hood](https://x.com/i/jf/under_the_hood).

## Published weights

Defaults in `param.rs` at the commit above:

| Positive | Weight | Negative | Weight |
| --- | ---: | --- | ---: |
| share via copy link | 20 | report | −234 |
| reply | 5 | mute author | −58.8 |
| quote | 5 | not interested | −47.52 |
| share via DM | 5 | block author | −31.2 |
| follow author | 4 | not dwelled | −0.02 |
| share | 2 | | |
| repost | 1 | | |
| like | 0.5 | | |
| continuous click dwell time | 0.4 | | |
| post click | 0.3 | | |
| open link | 0.2 | | |
| video open / photo expand / dwell | 0.07 / 0.05 / 0.05 | | |

Profile click and video quality view are 0. An original post from an account
the viewer mutually follows gets +15 on the reply weight (5 → 20).

Read them correctly:

- A weight multiplies one viewer's predicted probability, not a count. "One
  report cancels 468 likes" is explicitly wrong in the source; rare actions
  carry large weights so their prediction can matter at all.
- Negative weights are viewer actions (mute, not interested), not the
  sentiment of the text. There is no published positivity coefficient.
- The score cannot be reconstructed from visible counts; nothing measurable
  here is the ranking score.

## Claims not to encode

Treat these as unsupported unless new evidence appears: a fixed link penalty
(the code scores opening a link positively; X staff denied a link penalty in
July 2026, as reported); "links in replies bypass the algorithm"; a universal
best posting time, length or video duration; a hard early-engagement gate;
a Premium reach multiplier (X advertises reply prioritization, not a feed
multiplier); every reach drop being a shadowban; engagement pods or reply
counts as a lever. Experiments on the client's own account decide these.

## Review lenses for an X draft

Use in [content review](../review-marketer/references/content.md) when the
destination is X. Report each lens as observed / risk / direction for Writer
(through the client), label judgments as hypotheses and never rewrite the
text yourself. A lens that does
not fit the message's purpose is skipped, not forced.

- Worth sharing: would the target reader send it to a specific person or keep
  its link (a reference, a tool, a sourced number, a clear explanation)?
- Room to respond: is there an honest opening to reply or quote (a stance to
  add to, a real question), without engagement bait?
- Attention: does the first line earn the stop, and does the rest reward the
  reading time? Length is fine when it holds attention; padding is not.
- Reason to follow: does it show what this account is reliably for?
- Negative feedback risk: what would make the intended reader choose "not
  interested" or mute: off-topic for this audience, bait, a misleading hook,
  repetitive promotion, provocation for its own sake?
- Standalone value: a post with a link must say enough to be worth reading
  without the click.
- Cadence: several posts in a short window compete with each other in one
  viewer's feed (author diversity). Spacing is a hypothesis to test.

## Measuring

The `x` tool (sub-account, public data only) records and summarizes the
client's own posts: `snapshot` stores views, likes, replies, reposts, quotes
and bookmarks with the read time; `insights` compares them offline by post age,
format and posting hour. Shares, dwell, profile and link clicks, follows and
negative feedback are not visible there; views are not unique readers. Missing
is not zero. Compare posts at the same age; For You stops ranking a post after
48 hours, so most change happens before then. Interpret through
[Analyze](../analyze-marketer/SKILL.md); small samples stay inconclusive.

## Discovering conversations

Goal: places where the client can add something genuine, returned as
candidates (link, why it fits, suggested angle for Writer). The user replies.

- Topic sweeps and trends: `x_search` (xAI's semantic search over X).
- Exact queries and context: `x` `search` (Latest or Top) and `thread`. Its
  reads are paced and capped (shared with the Assistant): ask for what the
  question needs and never poll.
- Numbers for posts found elsewhere (an `x_search` citation, a competitor's
  launch): `x` `verify` with up to 50 post URLs or ids at once. It reads
  FxTwitter's public API outside the sub-account's caps and returns the real
  author, text and public counts; only `ok` rows are evidence.
- A reply reaches mostly that conversation's readers and the client's
  followers: For You drops replies from accounts a viewer does not follow.
  Conversations of mutual follows and posts still inside 48 hours are where a
  reply is most visible.
- Marketer never replies, quotes, likes, follows or DMs on X.
