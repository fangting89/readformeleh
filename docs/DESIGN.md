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
simple Mandarin). Never state anything not present in the letter itself.

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
