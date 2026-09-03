# Session scoring — judge walkthrough

Nomi is **not diagnosing**. After each meal check-in it applies the same
three evidence tracks, then takes the **maximum** (not an average) so a
help/pain cue cannot be washed out by “I’m fine.”

Text from the short follow-up chat is stored locally so language can be
scored without a cloud LLM.

## Labels

| Label | When | Suggested step |
|---|---|---|
| **As usual** | All three tracks are 0 | No extra step. |
| **Changed from usual** | The highest track is 1 | Message or call when convenient. |
| **Needs you now** | The highest track is 2 | Call or visit when you can. |

## Step A — What we keep from the meal

From this check-in, plus *her* recent meals as the reference (not a population):

| Feature | How it is computed |
|---|---|
| `latency_minutes` | First reply time − send time |
| `missed` | No reply before the next meal window |
| `wellbeing` | Exact reply `1`–`5` on the first turn, else null |
| `session_text` | Her 1–3 messages, lowercased for the lexicon |
| Personal usual | Median latency and median 1–5 from recent closed check-ins |

## Step B — Three evidence tracks (0 / 1 / 2)

### Track 1 — Rhythm

- **2** if `missed`
- **1** if `latency_minutes >= 2 × her median` (and the median exists)
- else **0**

### Track 2 — Self-report

- **2** if wellbeing is in `{1, 2}`
- **1** if wellbeing is `3` **and** her recent median is `>= 4`
- else **0** (including no number given)

### Track 3 — Language (`max(lexicon, tfidf_shift)`)

**3a Lexicon** (substring match on lowercased session text):

- **Level 2 (needs-you):** `help`, `hurt`, `pain`, `fall`, `fell`, `scared`, `cannot`, `can't`, `not ok`, `not okay`, `dizzy`, `chest`
- **Level 1 (drift):** `lonely`, `tired`, `cannot sleep`, `no appetite`, `worried`, `worse`
- **Usual cues** (never override 1 or 2; only used in reasons when language is 0): `ok`, `fine`, `good`, `ate`, `slept`, `alright`

If any level-2 phrase appears → language 2. Else if any level-1 phrase → language 1. Else 0 from the lexicon.

`cannot sleep` contains `cannot`, so it scores language **2** in this demo (level-2 wins). Keep `cannot sleep` on the level-1 list so judges can see the intended drift cue; the scorer does not try to be a linguist.

**3b Personal wording shift** (only if she has **≥ 2** prior scored session texts):

- Fit a TF-IDF vectorizer on *her* previous session texts (sklearn).
- Cosine similarity of this session vs the **mean** of those prior vectors.
- If similarity **< 0.35** → language at least **1**. Never **2** from TF-IDF alone.
- If fewer than two priors, skip (0 from this subcheck).

Why TF-IDF on stage: it counts how unusual her words are compared with *her last meals*, not compared with “patients on the internet.” `0.35` is a demo constant.

## Step C — Category (priority, not an average)

Do **not** average the three tracks.

1. If **any** track is 2 → **Needs you now**
2. Else if **any** track is 1 → **Changed from usual**
3. Else → **As usual**

That is the whole classifier.

## Step D — Recommended action

Each **fired** rule appends a reason sentence. The suggested step is looked up from the label only (table above). The caregiver card shows label + step + the exact reason list.

---

## Worked example 1 — Changed from usual

Meal sent 12:30. She replies at 13:55 (`latency = 85`). Texts: `3` then `a bit tired today` then `ok`. Her median latency 25, recent wellbeing 4.

- Rhythm: `85 >= 2 × 25` → **1**
- Self-report: `3` vs usual `4` → **1**
- Language: `tired` → lexicon **1**; fewer than two prior session texts → skip TF-IDF; stays **1**
- **Max = 1** → **Changed from usual**
- Step: Message or call when convenient.
- Reasons that fire: slower than usual; wellbeing dipped to 3; said `tired`. (`ok` does not override.)

## Worked example 2 — Needs you now

She writes `please help I fell`, with latency 5 minutes and wellbeing 4 (median 25 / 4).

- Rhythm: **0**
- Self-report: **0**
- Language: `help` and `fell` → lexicon **2**
- **Max = 2** → **Needs you now** even though she answered quickly with a 4.

## Honest limit

Lexicon + TF-IDF + latency is **auditable**, not medically validated.
