# ReadLeh — Design

## What this is

ReadLeh (from "leh" — a soft, casual Singlish sentence-particle used to
ask for a small favour, as in "help me read this leh") is a WhatsApp-native
bot that helps Singaporean seniors (and their caregivers) understand
official letters. The name is deliberate design work: it frames the ask as
a small, casual favour between friends, not a formal request to an
authority — which supports the stigma-lowering goal of the whole product.
A user photographs a government letter (CPF, IRAS, HDB, town council) and
sends it via WhatsApp; the bot replies with a short plain-language summary
— who it's from, what it says, what to do, by when — in English or
Mandarin.

## Why it exists (evidence base)

- Fei Yue Community Services (Senja Active Ageing Centre): staff estimate
  ~70% of their 1,400 seniors need help understanding official letters;
  each case takes 45min–2hr; letter help consumes ~20% of staff hours.
  Seniors prefer asking centre staff over "burdening" family.
  Source: LetterKey, GovTech Community Hackathon July 2025
  (community-hackathon.gov.sg/2025/letterkey).
- LetterKey built OCR+LLM summarization but delivered it as a kiosk at the
  AAC front desk / an app — seniors must physically go there. Their own
  interviews flagged technology adoption (new apps) as the core barrier.
  The gap this project fills: WhatsApp-native delivery. No app, no kiosk,
  no login — the channel seniors already use daily.
- SMU research (Nathan Peng, 2026): 4 in 5 older Singaporeans who qualify
  for public aid don't come forward, driven by stigma/fear of judgment.
  A private WhatsApp interaction lowers the social cost of asking for help.
- ScamShield Bot (GovTech/SPF, live on WhatsApp since 2023) already covers
  scam checking. This project does not rebuild it — see Design Decision 3.

## Architecture

WhatsApp (Twilio sandbox) → FastAPI webhook → pipeline: image → vision
model call (classify) → vision model call (extract + summarize) → reply
via Twilio.

Stateless: no database, no message logging, no image persistence. Each
letter is processed and discarded. The pipeline uses the Claude API
(Anthropic) for both the classification and summarization calls, reading
the letter photo directly.

## Design decisions

1. **Vision-native, not OCR+LLM.** Reading the letter photo directly
   handles skew, glare, tables, and mixed layout better than OCR on real
   phone photos. LetterKey used separate OCR+LLM steps; this project
   deliberately uses a vision-native model call instead. This is not
   retrieval-augmented generation — there is no retrieval; the photo
   itself is the grounding context.

   *Cost tradeoff, evaluated explicitly, not assumed away:* an OCR+text-LLM
   pipeline (e.g. Tesseract + a text-only call) would plausibly cut the LLM
   cost per letter several-fold, since image tokens dominate a vision
   call's cost versus the few hundred text tokens an extracted letter
   would need. At current pricing, a full classify+summarize round trip on
   one photo runs roughly 1–2 cents; at the evidence base's scale (~1,400
   seniors, a few letters/year each needing help) that's on the order of
   $30–50/year in API cost — already trivial in absolute terms. OCR's
   failure mode is exactly this product's core scenario (skewed, glared,
   poorly-lit phone photos from elderly users), which is the same failure
   mode that limited the prior kiosk solution. Trading a marginal,
   already-small cost saving for degraded accuracy on the hardest cases
   isn't a good trade, so OCR was rejected rather than not considered.
   What *is* implemented for efficiency: `pipeline/client.py` downscales
   images to a max 1568px edge before sending (Claude's vision token cost
   scales with pixel count; resolution beyond that doesn't improve reading
   accuracy on a document photo). Prompt caching between the classify and
   summarize calls was evaluated and rejected — the two calls have
   different system prompts and tool declarations, so Anthropic's cache
   (which requires an identical prefix) would never hit, and a cache
   *write* costs more than a plain input token, making it strictly worse
   than doing nothing without a larger restructure into a shared-prefix
   conversation. Also considered: merging classify+summarize into one call
   with an optional summary field, which would roughly halve image-token
   cost — rejected because it downgrades the safety gate from
   "structurally impossible to generate a scam summary" (today, if
   `classify_letter` returns `suspicious`, `summarize_letter` is simply
   never called) to "the model was told to leave a field empty," for a
   saving that's already trivial in absolute terms. Caching the (small,
   per-function) system prompt itself was also tried and empirically
   verified via the API's `usage.cache_read_input_tokens` field to be a
   no-op — the prompt falls below Anthropic's minimum cacheable content
   size, so nothing gets cached either way. Not kept, since a cache marker
   that provably does nothing is worse than no marker at all.

   Also benchmarked `claude-haiku-4-5` against `claude-sonnet-5` (then the
   default) for both steps. For classify: matched Sonnet on all 6 samples,
   including correctly flagging the scam specimen with a thorough red-flag
   list. For summarize: matched on 3 of 4 repeated runs on the same clean
   letter; one run stated a CPF balance incorrectly (off by a factor of
   ~2), not reproduced on 3 follow-up runs — evidence of a small,
   non-systematic numeric-hallucination risk, likely present at some rate
   regardless of model tier, not something the "flag uncertainty" prompt
   rule catches since it wasn't a bad-photo case. Also observed: on the
   deliberately blurred sample, Haiku consistently abandons the fixed
   output structure and replies in plain prose asking for a clearer
   photo, rather than following the template with a hedged value. Arguably
   safer than guessing, but a format inconsistency worth handling
   explicitly in the Phase 2 message-formatting pass rather than left
   implicit.

   At current pricing, Haiku 4.5 ($1/$5 per MTok in/out) is exactly half
   the cost of Sonnet 5's introductory rate ($2/$10 per MTok, in effect
   through 31 Aug 2026) — a real but modest saving given the already-small
   absolute cost (roughly half a cent per letter). Given this project runs
   on personal API budget rather than an org's, and both classify (bounded
   categorical decision) and summarize (templated extraction, not
   open-ended reasoning) fit Anthropic's own stated guidance for
   Haiku-appropriate tasks, `pipeline/client.py`'s default `MODEL` is
   `claude-haiku-4-5-20251001` for both calls. `classify_letter` also
   accepts a `model` override for further comparison if needed. Revisit
   if real-letter testing surfaces wrong figures in a summary — that's a
   real deployment concern, not a purely a hypothetical one.

   **Follow-up (25 Jul 2026): the numeric-hallucination risk above is now
   mitigated, not just named.** `pipeline/summarize.py`'s
   `summarize_letter_checked` reads a `clear`-quality letter twice,
   independently, and compares the two reads' By-when date and action
   amount (`pipeline/summary_fields.py`). Any field that disagrees between
   the two is replaced with the same hedge sentence `summarize_letter`
   already uses for a field it can't read at all — a disagreement between
   two independent reads is exactly as untrustworthy as an admitted guess,
   so it's treated the same way rather than picking one read arbitrarily.
   This doubles the summarize call for `clear`-quality letters only
   (roughly another half-cent), which is still trivial in absolute terms
   at this project's scale. It does not eliminate the risk entirely (both
   reads could coincidentally make the same misread), but it closes the
   specific failure mode the CPF-balance incident above demonstrated: a
   *single* confidently-wrong read going out unchallenged.
2. **Privacy by design.** Letters contain NRIC numbers, addresses, money
   figures. Nothing is stored. Prompts instruct the model to never repeat
   NRIC numbers or full addresses in summaries. No logging of message
   content or images, even in debug — log event types only.
3. **Scam-check as a safety layer, not a feature.** Before summarizing,
   classify the letter: genuine-government / bill-or-medical / suspicious /
   unreadable. If suspicious, do not summarize (a plain-language summary of
   a scam letter helps the scammer). Instead: warn gently, list the red
   flags noticed, and refer to the ScamShield helpline 1799. This
   complements ScamShield rather than competing with it. `red_flags` are
   required to describe each issue generically (e.g. "asks the reader to
   confirm their NRIC number"), never quoting the actual NRIC/address/
   amount from the letter — this keeps them safe to log for debugging
   without violating Design Decision 2.

   **Known limitation, observed live, now fixed:** the same photo of a
   genuine letter was classified `suspicious` on one run and `government`
   on an identical re-run minutes later — `classify_letter` wasn't setting
   a `temperature`, so it was using the API default, which allowed enough
   run-to-run variance to flip the one decision in this pipeline that's
   actually safety-critical. Fixed by setting `temperature=0` on the
   classify call (variation is still fine for `summarize_letter`'s prose,
   not for this categorical decision).

   **A second, more serious gap, found by building an eval harness (see
   `eval/`), also now fixed:** `classify_letter`'s `category` only answers
   "can I tell what kind of letter this is and who it's from". It does
   not answer "can I safely read out the *specific* amounts and dates in
   this letter." Those turned out to be different bars. On a moderately
   degraded (blurred, rotated) but still confidently-categorizable photo,
   `summarize_letter` was run 5 times in stress-testing and produced a
   *different wrong dollar amount and wrong date almost every time*,
   formatted with the same confidence as a correct summary, e.g. stating
   "$50.63" and "25 January" against a real letter that actually said
   $89.50 due 25 Jul 2026. Two rounds of prompt-only fixes (forbidding
   guessed/approximate figures, forbidding invented payment methods) did
   not close this reliably.

   The fix was architectural, not another prompt tweak: `classify_letter`
   now also returns an independent `image_quality: "clear" | "degraded"`
   assessment. `app/main.py` skips `summarize_letter` entirely whenever
   `image_quality` is `"degraded"`, exactly like it already does for
   `category == "suspicious"` or `"unreadable"`. A photo can be clear
   enough to categorize while still being too degraded to safely extract
   figures from, and the pipeline now gates on the stricter of the two
   bars, not just the first one. Verified via `eval/run_eval.py`: 1.0
   image_quality-gate accuracy and 0 remaining amount/date errors across
   the full golden set after the fix.

   **Prompt-injection hardening (25 Jul 2026).** The entire threat model
   here is that the letter photo is attacker-controlled input, yet neither
   system prompt originally said anything about that. Both
   `classify_letter`'s and `summarize_letter`'s system prompts now
   explicitly instruct the model to treat all text visible in the
   photographed letter as untrusted content to analyze, never as
   instructions to follow — and that a letter attempting to instruct the
   classifier directly (e.g. a fake "SYSTEM:" line telling it to output
   `category: government`) is itself a red flag for `suspicious`, not
   something to comply with. `eval/dataset.py`'s `scam_prompt_injection`
   specimen exercises exactly this: a fake government letter whose body
   contains such an override attempt. It classifies `suspicious` 3/3 in
   `eval/run_eval.py`, with the injection attempt itself listed among the
   red flags (described generically, per Design Decision 2 — the
   injection text itself is never quoted back).
4. **Scope discipline.** v1 languages: English + Mandarin only. Malay,
   Tamil, and dialect audio (Hokkien/Cantonese) are named roadmap items,
   not v1 features. Twilio sandbox for the demo; the production path
   (WhatsApp Business API verification, PDPA review, AAC partnership) is
   documented but not built.
5. **Bilingual by default, not asked for.** The obvious alternative —
   asking "English or Chinese?" on first contact — has the same flaw it's
   meant to solve: a sender who can't read English well enough to
   understand the letter may not understand the question either, and it
   adds a round trip for someone the evidence base already shows is
   friction-sensitive. Instead: a sender's first summary is bilingual
   (English + Mandarin shown together); replying "中文"/"English" once
   remembers that preference for later summaries (a lasting exception to
   statelessness, unlike the short-TTL last-summary cache — a person's
   language doesn't go stale in 10 minutes). Costs one extra text-only
   `translate_summary` call per first-contact letter versus a known
   preference, which is cheap relative to the vision call and worth it to
   never risk a sender not understanding the bot's own instructions.
6. **Escalate after repeated unreadable photos, don't just repeat the same
   tip (25 Jul 2026).** The evidence base above (Fei Yue/Senja AAC) shows
   seniors already fall back on in-person help when something doesn't
   work over a channel — the whole reason letter help consumes ~20% of
   staff hours today. A bot that keeps replying "try again with better
   lighting" to someone who has already failed once is asking them to
   solve a problem they've already shown they can't solve alone over this
   channel. `app/state.py`'s `ConsecutiveFailureCount` tracks unreadable/
   degraded results per sender (30 min TTL, so an old streak doesn't
   silently carry into a new session); after 2 in a row, `app/main.py`
   sends `messages.UNREADABLE_RETRY_ESCALATED` instead of the baseline
   retry tip, suggesting a family member or the nearest Active Ageing
   Centre. The streak resets on any legible result (a successful summary,
   or a letter correctly classified suspicious) — it should reflect
   "recent trouble with this channel," not accumulate forever. Deliberately
   webhook-only: `pipeline/run.py`'s CLI entrypoint is a one-shot process
   with no sender identity across invocations, so there's no streak to
   track there.

## Output format for summaries (fixed structure)

```
📬 This letter is from [agency].
Action needed: [Yes — one short line on what to do, or "No, nothing to do!"]
What it says: [3–4 short sentences, each one idea, plain words, no unexpanded acronyms]
By when: [date, or "No action needed."]
[amount involved, if any]
[If the letter shows an enquiry phone number: "Questions? Call [agency] at [number]."]
Note: [Always present — an automated-summary disclaimer, e.g. "This is an
automated summary — for anything important, please check the original
letter or contact [agency] directly."]
```

Action-needed leads the summary, before the explanation — that's usually
the reader's first worry, so it's resolved before anything else. Elder-
friendly formatting: short lines, one idea per sentence (not just simple
words — a multi-clause sentence is still harder to parse), consistent
terminology for the same concept throughout, key action bolded, no walls
of text. Reading level: simple everyday English (or simple Mandarin) —
section labels are translated too, not left in English. Never state
anything not present in the letter itself: if the photo is too blurry or
angled to be confident about a specific date, amount, or other fact, the
summary says so explicitly rather than guessing.

## Roadmap

- **Core pipeline**: classification + summarization, tested against
  varied real letters including bad-quality photos and scam specimens.
- **WhatsApp integration**: webhook flow, language toggle, graceful
  handling of non-image messages and unreadable photos.
- **Audio replies** (not in v1): voice-note playback of summaries.
  User testing from LetterKey found seniors preferred audio (3/4 testers
  rated 5/5) — a strong signal for a future iteration.
- **Production path**: Meta WhatsApp Business API verification (~14 days),
  PDPA review, AAC pilot partnership, per-message cost modelling —
  individual developers can't easily self-verify a WhatsApp Business
  number, so real deployment would go through a partner organisation.

## Watch-outs

- Twilio sandbox testers must re-join every 72h.
- Test with genuinely bad photos (shadow, angle, glare) — that's what
  real senior-taken photos look like; graceful handling is part of the
  product's value.
- Never commit real letters with personal details; never log content.
- The bot must never summarize a suspicious letter "just in case" — when
  classification is uncertain between government and suspicious, prefer
  the cautious path (warn + verify via official channels).
