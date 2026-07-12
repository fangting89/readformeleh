# Letter Kaki — Design

## What this is

Letter Kaki ("kaki" — Singlish for a trusted buddy/companion, from Malay;
e.g. "makan kaki") is a WhatsApp-native bot that helps Singaporean seniors
(and their caregivers) understand official letters. The name is deliberate
design work: it positions the bot as a friend helping out, not an authority
explaining down — which supports the stigma-lowering goal of the whole
product. A user photographs a government letter (CPF, IRAS, HDB, town
council) and sends it via WhatsApp; the bot replies with a short
plain-language summary — who it's from, what it says, what to do, by when —
in English or Mandarin.

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
2. **Privacy by design.** Letters contain NRIC numbers, addresses, money
   figures. Nothing is stored. Prompts instruct the model to never repeat
   NRIC numbers or full addresses in summaries. No logging of message
   content or images, even in debug — log event types only.
3. **Scam-check as a safety layer, not a feature.** Before summarizing,
   classify the letter: genuine-government / bill-or-medical / suspicious /
   unreadable. If suspicious, do not summarize (a plain-language summary of
   a scam letter helps the scammer). Instead: warn gently, list the red
   flags noticed, and refer to the ScamShield helpline 1799. This
   complements ScamShield rather than competing with it.
4. **Scope discipline.** v1 languages: English + Mandarin only. Malay,
   Tamil, and dialect audio (Hokkien/Cantonese) are named roadmap items,
   not v1 features. Twilio sandbox for the demo; the production path
   (WhatsApp Business API verification, PDPA review, AAC partnership) is
   documented but not built.

## Output format for summaries (fixed structure)

```
📬 This letter is from [agency].
What it says: [3–4 short sentences, plain words, no unexpanded acronyms]
What you need to do: [action, or "Nothing! ..." if none]
By when: [date, or "No action needed."]
[amount involved, if any]
```

Elder-friendly formatting: short lines, one idea per line, key action
bolded, no walls of text. Reading level: simple everyday English (or
simple Mandarin) — section labels are translated too, not left in English.
Never state anything not present in the letter itself: if the photo is too
blurry or angled to be confident about a specific date, amount, or other
fact, the summary says so explicitly rather than guessing.

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
