# Letter Kaki: Interview Prep Summary

Personal study reference. Full technical source of truth is
[docs/DESIGN.md](docs/DESIGN.md); this file condenses it plus adds status,
scalability, and Q&A prep that DESIGN.md doesn't cover.

## 1. Elevator pitch

Letter Kaki is a WhatsApp bot that helps Singaporean seniors understand
official letters (CPF, IRAS, HDB, town council). You photograph the letter,
send it on WhatsApp, and get back a short plain-language summary (who it's
from, what it says, what to do, by when) in English and Mandarin, with a
scam-detection safety gate that withholds a summary (and refers to
ScamShield) instead of ever explaining a scam letter in plain language. It's
a deliberately non-agentic, safety-gated LLM workflow (two-to-three fixed
vision-LLM calls behind hard-coded control flow — a third, independent
read is added for image-quality-`clear` letters specifically to catch a
rare hallucinated figure, see §5 — not an autonomous agent), because a
bounded, safety-critical task like this shouldn't have a model improvising
its own steps.

## 2. Problem statement & evidence base

- **Fei Yue Community Services (Senja Active Ageing Centre):** staff
  estimate ~70% of their 1,400 seniors need help understanding official
  letters; each case takes 45min–2hr; letter help consumes ~20% of staff
  hours. Seniors prefer asking centre staff over "burdening" family.
  (Source: LetterKey, GovTech Community Hackathon, July 2025.)
- **LetterKey's gap:** they built OCR+LLM summarization but delivered it as
  a kiosk at the AAC front desk / an app; seniors had to physically go
  there. Their own interviews flagged technology adoption (new apps) as the
  core barrier. **This is the gap Letter Kaki fills:** WhatsApp-native
  delivery: no app, no kiosk, no login, the channel seniors already use
  daily.
- **SMU research (Nathan Peng, 2026):** 4 in 5 older Singaporeans who
  qualify for public aid don't come forward, driven by stigma/fear of
  judgment. A private WhatsApp interaction lowers the social cost of asking.
- **ScamShield Bot** (GovTech/SPF, live on WhatsApp since 2023) already
  covers scam *checking*. Letter Kaki deliberately does not rebuild it; it
  complements it (see Design Decision 3 below).

**Broader context: why this matters now, not just for letters.**
Singapore becomes a *super-aged* society in 2026 (this year), with one in
five residents aged 65+, per UN World Population Prospects. A Duke-NUS
Centre for Ageing Research and Education study found two in five
Singaporeans aged 62+ report loneliness, roughly 6% are socially
disconnected, and, notably, many seniors feel isolated *even while living
with family*. That last point matters specifically for this project: "just
get your kids to read it for you" isn't a real safety net for a large share
of the target group, which is exactly why a channel that doesn't route
through family has independent value, not just convenience value. Letter
comprehension is one visible symptom of a broader pattern: seniors lack a
low-friction channel for several kinds of support, not only paperwork (this
is the seed of the platform idea in §10 below).
*(Sources, gathered for interview prep, not part of the original project
evidence base in docs/DESIGN.md:
[Duke-NUS: social isolation, loneliness biggest enemy for seniors](https://www.duke-nus.edu.sg/care/news-events/news/articles/the-problem-with-being-alone-social-isolation-loneliness-biggest-enemy-for-seniors-in-s-pore),
[UN WPP via NationThailand: Singapore super-aged 2026](https://www.nationthailand.com/blogs/lifestyle/health-wellness/40033648).)*

## 3. How it works

1. User sends a photo of a letter on WhatsApp.
2. Bot acks immediately ("Reading your letter, one moment 🙏 / 正在看您的信，请稍等 🙏").
3. `classify_letter` (vision call) sorts it into `government` /
   `bill_or_medical` / `suspicious` / `unreadable`.
4. If `suspicious`: **stop**, send a warning + red flags + refer to
   ScamShield 1799. No summary is generated. If `unreadable`: ask for a
   clearer photo with a lighting tip.
5. Otherwise `summarize_letter` (vision call) extracts a fixed-format
   summary; first contact gets both languages, later ones respect a
   remembered preference.

Fixed output template:
```
📬 This letter is from [agency].
Action needed: [Yes, one short line, or "No, nothing to do!"]
What it says: [3–4 short sentences, one idea each, no unexpanded acronyms]
By when: [date, or "No action needed."]
[amount involved, if any]
[Only if a real phone number is visible: "Questions? Call [agency] at [number]."]
Note: [always present — automated-summary disclaimer]
```
Action-needed leads: that's the reader's first worry, resolved before
anything else. Same word for the same concept throughout; key action
bolded; never states anything not present in the letter (if a detail is
unclear from a bad photo, it says so rather than guessing).

## 4. Architecture

```
WhatsApp ⇄ Twilio (sandbox) ⇄ FastAPI webhook (app/main.py)
                                    │
                                    ▼
                          classify_letter()  (safety gate)
                                    │
                        (government/bill_or_medical)    (suspicious: warn
                                    │                     + 1799, STOP)
                                    ▼                     (unreadable: retry
                          summarize_letter()               prompt, STOP)
                                    │
                          translate_summary() (if zh needed)
                                    │
                                    ▼
                          reply via Twilio REST API
```

**Stateless by design**, with 5 documented, deliberate in-memory exceptions
(`app/state.py`):
- `LanguageCache`: last summary text per sender, 10 min TTL (lets a
  language toggle re-render without re-uploading the photo).
- `LanguagePreference`: remembered once a sender replies "中文"/"English",
  **no TTL** (a person's language doesn't go stale).
- `RateLimiter` (5 requests/10 min/sender) + `SeenMessages` (idempotency
  against Twilio's webhook retries): cost/abuse guardrails.
- `ConsecutiveFailureCount` (30 min TTL): counts unreadable/degraded
  results per sender so the retry message can escalate to suggesting
  in-person help after 2 in a row, instead of repeating the same lighting
  tip indefinitely (see §5, the escalation design decision).

No database. No message logging. No image persistence: each letter is
processed and discarded.

## 5. Key design decisions & tradeoffs (the 30-second version)

- **Vision-native, not OCR+LLM.** Claude reads the photo directly, handling
  skew/glare/tables better than OCR on real phone photos, which is exactly
  the hardest real scenario (elderly users, imperfect photos) and the same
  failure mode that limited LetterKey's kiosk. Cost is ~1–2¢/letter
  (~$30–50/yr at the evidence-base's scale); OCR would cut that further,
  but trading an already-trivial saving for degraded accuracy on the
  hardest cases isn't a good trade. Not RAG: no retrieval, the photo
  itself is the only grounding context.
- **Haiku 4.5 over Sonnet 5**, benchmarked, not assumed: matched Sonnet on
  all 6 classify samples (including the scam specimen); matched on 3/4
  summarize runs, with one non-reproduced numeric slip (a CPF balance off
  by ~2x) — a known, named residual risk at the time, since **mitigated**
  (not eliminated) by `summarize_letter_checked` (see below). Both tasks
  (bounded categorical decision; templated extraction) fit Anthropic's own
  Haiku-appropriate guidance, so the cost saving was taken.
- **Scam gate is architecture, not a prompt suggestion.** If
  `classify_letter` returns `suspicious`, `summarize_letter` is
  structurally never called: the code branches, not "the model was told
  not to." This is the single most defensible safety claim in the project.
- **Privacy by design.** Nothing stored; no logging of content or images
  even in debug; red flags for suspicious letters are required to be
  described generically (e.g. "asks for NRIC") so even the safety log
  never contains a real NRIC/address/amount.
- **Bilingual by default, not asked for.** Asking "English or Chinese?" has
  the same flaw it's meant to solve: someone who can't read English well
  enough to understand the letter may not understand the question either.
- **The temperature=0 fix** (made 25 Jul, this session): `classify_letter`
  had no temperature set, and DESIGN.md documented a live bug: the same
  photo flipped between `suspicious` and `government` on identical re-runs.
  That's the one safety-critical decision in the whole pipeline. Fixed by
  pinning `temperature=0` on that call only (summarize keeps default
  variation, fine for prose, not for a categorical safety decision). Good
  "found and fixed my own bug before it became someone else's problem"
  story.
- **The image_quality gate** (added 25 Jul 2026, via the eval harness
  below): `classify_letter`'s `category` answers "what kind of letter is
  this," not "can I safely read the specific figures in it": those
  turned out to be different bars. Fixed by adding a second, independent
  `image_quality: clear | degraded` field, and gating `summarize_letter`
  on it the same way `category == suspicious` is already gated. Full
  story in §6.
- **The self-consistency hallucination guard** (added 25 Jul 2026): even
  on `image_quality: clear` letters, a single wrong read can still slip
  through confidently formatted (the CPF-balance incident above).
  `summarize_letter_checked` reads the letter twice, independently, and
  hedges any By-when date or dollar amount that disagrees between the two
  reads instead of trusting either one blindly. Doubles the summarize
  call for clear-quality letters (~half a cent more); mitigates the risk,
  doesn't claim to eliminate it (both reads could coincidentally agree on
  the same wrong figure).
- **Prompt-injection resistance** (added 25 Jul 2026): the whole threat
  model here is that the letter photo is attacker-controlled input, so
  both system prompts now explicitly treat all text in the photo as
  untrusted content, never as instructions — and flag any attempt to
  instruct the classifier directly (e.g. a fake "SYSTEM:" line) as itself
  a red flag. Proven with a dedicated adversarial eval specimen
  (`scam_prompt_injection`), caught `suspicious` 3/3.
- **Escalation after repeated unreadable photos** (added 25 Jul 2026): a
  bot that repeats the same lighting tip to someone who's already failed
  once isn't actually helping — the evidence base already shows this
  population falls back on in-person help when a channel doesn't work.
  After 2 consecutive unreadable/degraded results from the same sender,
  the retry message escalates to suggesting a family member or the
  nearest Active Ageing Centre. `pipeline/run.py`'s CLI deliberately
  doesn't get this — no cross-invocation sender identity to track a
  streak against.

## 6. Evaluation

**Industry framing first, since "how do you evaluate a non-deterministic
LLM pipeline" doesn't have a data-science-accuracy-metric answer by
default.** The two pipeline steps need different eval strategies:
`classify_letter` is a genuine categorical decision, so precision/recall/
F1 apply directly, same as any ML classifier (the accuracy-metric
approach *does* map on cleanly here). `summarize_letter` is generative,
so there's no single correct wording; industry practice there is
golden-field extraction accuracy, format compliance, and consistency/
self-agreement checks, not classic NLG metrics (BLEU/ROUGE are widely
considered weak for this and mostly abandoned). LLM-as-judge is the
standard fallback when ground truth can't be matched exactly, deliberately
not used here: every specimen's expected fields are exact because the
letter text is authored, not photographed, so exact-substring scoring is
possible and more reproducible than a second LLM's judgment would be.

**No large collected dataset was needed.** `eval/dataset.py` is a single
source of truth of 14 synthetic specimens (4 government, 2 bill/medical,
4 scam variants — including one prompt-injection attempt, see §5 — and 4
degraded-photo variants) with exact expected fields, since the letter
text is authored, not collected. `scripts/generate_samples.py` renders
them into `samples/*.jpg` from that same registry, so the fixtures and
the ground truth can't drift apart. `eval/run_eval.py` runs
`classify_letter` 3x and `summarize_letter` 2x per applicable specimen
and scores deterministically against the known fields.

**Final numbers** (`eval/results/latest.json`, current as of this
session): classify 1.0 accuracy across 42 trials (all 4 classes, 0 flips
across repeats, confirming the temperature=0 fix holds, including the
prompt-injection specimen caught `suspicious` 3/3); image_quality gate
1.0 accuracy across 21 trials; summarize 1.0 pass rate on action-needed
correctness, agency mention, format compliance (including the new
mandatory disclaimer line), amount accuracy, and deadline accuracy (12
runs, with a date-formatting normalization fix so "31 Aug" vs
"31 August" isn't scored as wrong).

**What actually made this worth building, not the final clean numbers.**
The eval didn't just confirm things worked, it changed the pipeline
twice:
1. **A mislabeled test, caught by inspection.** The original
   "bad_quality_photo" specimen was labeled expecting `category:
   unreadable`. The model classified it `government` 3/3 times, which
   looked like a failure until manual inspection showed a human can read
   the photo too; the label was wrong, not the model. Relabeled, and a
   genuinely harder `heavy_blur_notice` specimen was added to keep real
   coverage of the unreadable path.
2. **A real hallucination risk, caught by repeated runs.** With the label
   fixed, `summarize_letter` was stress-tested 5x against that same
   moderately-blurry photo. It produced a *different wrong dollar amount
   and wrong date almost every run* ("$50.63", "25 January", "$82.50 for
   2024" against a real $89.50 due 25 Jul 2026), confidently formatted.
   Two rounds of prompt-only fixes didn't reliably close it. The actual
   fix was architectural: `classify_letter` now returns a second,
   independent `image_quality` field, and `summarize_letter` is skipped
   whenever it's `degraded`, regardless of category (see docs/DESIGN.md
   Design Decision 3 and pipeline/classify.py). This is the single most
   defensible "found a real safety gap, not a hypothetical one" story in
   the whole project, and it exists specifically because building the
   eval forced repeated runs against a hard case instead of a single
   spot-check.

Run it yourself: `uv run python -m eval.run_eval` (regenerates nothing;
run `uv run python -m scripts.generate_samples` first if `eval/dataset.py`
changed). Costs a small amount of real API spend, all Haiku-priced.

## 7. Codebase map

**`pipeline/`**: the core LLM pipeline, no FastAPI/Twilio imports.
- `client.py`: shared Anthropic client (`get_client`), image encoding +
  downscale to 1568px max edge (vision cost scales with pixel count, extra
  resolution doesn't improve reading accuracy on a document photo).
- `config.py`: `require_env()`, fail-fast env var access, used everywhere
  instead of raw `os.environ`.
- `classify.py`: the safety gate; forced tool-use call returning
  `{category, image_quality, red_flags}`. `image_quality` is the second,
  independent gate added via the eval harness (§6).
- `summarize.py`: the templated vision call (`summarize_letter`) plus a
  text-only `translate_summary` used for the WhatsApp language toggle
  (re-renders from a cached summary, no image re-upload).
- `run.py`: CLI entrypoint: `python -m pipeline.run photo.jpg --lang zh`.

**`app/`**: the FastAPI web layer, thin (no prompt logic).
- `main.py`: webhook route: signature verification, idempotency/rate-limit
  checks, background-task dispatch (`_process_letter` runs off the
  request/response cycle so a multi-second classify+summarize round trip
  doesn't block the event loop).
- `state.py`: the 5 in-memory stores described above.
- `messages.py`: static bilingual reply templates (ack, usage
  instructions, suspicious warning, unreadable retry, rate-limited,
  processing error).
- `twilio_client.py`: Twilio-specific I/O: webhook signature verification,
  media download, outbound send.

**`tests/`**: 51 passing tests (pytest), deterministic logic only: config,
client, classify tool schema, summary-field parsing/reconciliation
(`test_summary_fields.py`), the self-consistency guard's wiring
(`test_summarize.py`), state stores, webhook routing (including the
image_quality gate and the escalation counter). LLM output *quality* is
deliberately not asserted in unit tests (not deterministic enough to be
meaningful) — even the guard's tests run against synthetic, hand-written
summary strings, not live model output; that's judged via the eval
harness and the notebook instead.

**`eval/`**: the eval harness (§6). `dataset.py` is the single source of
truth for the 14-specimen golden set and its exact expected fields;
`run_eval.py` scores `classify_letter`/`summarize_letter` against it and
writes `results/latest.json`.

**`scripts/generate_samples.py`**: renders `eval.dataset.SPECIMENS` into
`samples/*.jpg` (normal, blurred, heavy-blur, low-light, and partial-crop
renders), so the fixtures and the eval's ground truth share one source
and can't drift apart.

**`notebooks/01_pipeline_check.ipynb`**: runs classify+summarize over
every sample in `samples/`, the way individual outputs get eyeballed
during prompt iteration (complementary to `eval/`'s aggregate scoring,
not a replacement for it). Designed to be re-run live after prompt
changes — outputs aren't committed.

**`notebooks/02_eval_insights.ipynb`** (added 25 Jul 2026): the opposite
convention — executed once and committed *with* its outputs, so the
classify/summarize metrics, the prompt-injection specimen's result, and a
targeted raw-vs-guarded comparison of `summarize_letter_checked` are all
readable later without re-running anything or spending more API budget.

**`docs/DESIGN.md`**: the full source-of-truth design doc (evidence base,
architecture, all 6 design decisions with full reasoning, roadmap,
watch-outs). This file is a condensed companion to it, not a replacement.

## 8. Status

- **Phase 1 (core pipeline): done.** `pipeline/classify.py`,
  `summarize.py`, `run.py`.
- **Phase 2 (WhatsApp integration): done.** FastAPI webhook, Twilio
  signature verification, bilingual-by-default flow, language toggle, rate
  limiting, idempotency. Confirmed working live on WhatsApp (Twilio
  sandbox).
- **Eval harness: done** (25 Jul 2026, post-Phase-2). Not part of the
  original phase plan; built after realizing "how do you evaluate this"
  needed a real answer. Directly caused two pipeline fixes (see §6), not
  just measurement after the fact.
- **Phase 3 (audio/TTS): deliberately dropped**, not deferred. Decided
  12 Jul 2026 to keep the deadline-bound scope to text-only summaries
  rather than treat audio as a stretch goal.
- **Phase 4 (portfolio material): not started.** Demo video (60s: happy
  path CPF letter, then scam catch) and the written portfolio piece
  (objective/design/outcome/reflection) are the remaining work before the
  31 Jul 2026 deadline.

## 9. Deployment & scalability

**Current state:** Twilio WhatsApp *sandbox* (test-mode number, testers
must re-join every 72h), FastAPI running locally, exposed via ngrok.

**Path to real production:** WhatsApp Business API verification (~14
days), PDPA review, an AAC partnership (an individual developer can't
self-verify a WhatsApp Business number; real deployment would go through a
partner organisation), per-message cost modelling.

**Scalability, stated honestly (this is the most likely "how would this
scale" follow-up, worth naming unprompted):**
- The pipeline itself is stateless and cheap to scale horizontally (each
  letter is an independent classify+summarize call).
- **But** the 5 in-memory stores in `app/state.py` don't survive a process
  restart and won't work correctly across multiple app instances (a sender
  routed to a different instance loses their language preference / rate
  limit state / dedup cache). Moving to an external store (Redis) is the
  known fix, not yet built; v1 is single-instance by design.
- No structured monitoring/metrics beyond `logger.info`/`logger.exception`
  calls; no load testing has been done.
- Cost scales linearly per letter (the vision call dominates cost); the
  rate limiter (5 requests/10 min/sender) is the only cost guardrail today.

This is *technical* scalability (more letters, more instances). For
*product* scalability, what else this could become, see §10 below.

## 10. Vision / roadmap: from Letter Kaki to a "super WhatsApp bot" for seniors

*Not built: this is where the project's core insight generalizes, worth
raising if asked about long-term vision. Keep it explicitly framed as
roadmap thinking, not a claim about what exists today.*

**The actual insight isn't the LLM pipeline, it's the channel.**
LetterKey already proved seniors need letter help and already built an
LLM pipeline for it; it failed on adoption because it lived in a
kiosk/app. WhatsApp fixes that for letters specifically. But the same
adoption barrier ("the service exists, but only if you already know to
seek it out through an app, a hotline, or a physical visit") shows up in
at least two other real, already-funded senior services in Singapore:

- **Befriending / social connection.** AIC and partner organisations
  (Lions Befrienders, Blossom Seeds, TOUCH Community Services and others)
  already run structured befriending programmes: volunteers are matched
  to seniors at risk of isolation for regular check-ins (home visits or
  calls), and AIC is piloting block-level "Community Befriending Groups."
  Today, getting matched runs through a hotline, an AAC visit, or being
  flagged by a case worker. A WhatsApp message as simple as "I'd like
  someone to talk to" that captures interest and refers into AIC's
  existing befriending pipeline is the identical fix as Letter Kaki,
  applied to a second service: a new front door onto a service that
  already exists, not a new social service.
- **Activity discovery.** There are 230+ Active Ageing Centres islandwide
  running free programmes (exercise, arts and crafts, cooking, adapted
  sports), but finding one today means a postal-code map search on a
  website or a hotline call. "What's on near me this week?" as a WhatsApp
  query is the same fix again, sitting on top of AIC's own activity
  repository rather than a new content source.

**Why this is a coherent platform idea, not scope creep:** every module
would follow the same design DNA already validated in Letter Kaki:
*complement existing services, don't rebuild them* (same posture as the
ScamShield relationship: route to AIC/Lions Befrienders rather than build
a volunteer-matching engine from scratch), and *safety-gate before
acting* (a message suggesting a medical emergency should surface 995/999
immediately, not get routed into a "find a befriender" flow: the same
shape as the suspicious-letter gate that refers out rather than trying to
resolve things itself). Architecturally this would mean adding a
lightweight intent router ahead of today's single-purpose classify step:
a photo → today's letter pipeline; "I need help/company" → befriending
referral; "activities near me" → AAC lookup.

**Honest caveats, worth naming unprompted:** each new module is real
added scope, not a free extension. Letter Kaki's privacy story ("nothing
is stored, letter is processed and discarded") gets harder once the bot
is forwarding a senior's stated needs or location to a third party for
befriender matching; that's a PDPA-relevant data flow the current
architecture doesn't have. An activity/befriending directory needs a
genuine data-sharing relationship with AIC, not something a solo
portfolio project can stand up unilaterally. This is the answer to
"where could this go with more time and a real partner org," not a claim
about what's built.

*(Sources, gathered for interview prep:
[AIC: Befrienders](https://www.aic.sg/Age-Well/Learning-and-Volunteerism/Volunteering-Opportunities/Befrienders),
[Lions Befrienders](https://www.lionsbefrienders.org.sg/),
[AIC: Active Ageing Centres](https://www.aic.sg/care-services/active-ageing-centres).)*

## 11. Known limitations / what I'd do differently

- No persistent state (see above): fine for a portfolio demo, a real
  named limitation for production.
- No observability beyond basic event logging; no metrics/alerting.
- Twilio sandbox only, not yet a real WhatsApp Business number.
- Phase 4 (demo + write-up) still pending as of this document.
- The eval golden set (14 specimens) is synthetic and hand-authored, not
  drawn from real usage. It's what caught two real bugs (§6), but it's
  still a much smaller and narrower distribution than real seniors'
  photos would produce. Growing it from actual (consented, redacted)
  usage is the natural next step once there's real traffic to learn from.
- Single developer, no code review: a portfolio-project constraint, worth
  naming plainly rather than implying otherwise.

## 12. Likely interview questions + terse answers

**"How do you evaluate an LLM pipeline, since it's not deterministic?"**
Split by task: `classify_letter` is a real categorical decision, so
precision/recall/F1 apply directly (accuracy metrics genuinely do map on
here). `summarize_letter` is generative, so I score golden-field
extraction accuracy and format compliance against a synthetic, exactly-
known-ground-truth set instead of classic NLG metrics, deliberately
skipping LLM-as-judge since exact-substring scoring is possible and more
reproducible here. It's not just a measurement exercise: building it
caught a mislabeled test (§6) and a real hallucination risk that two
rounds of prompt fixes didn't close, which needed an architecture change
(the image_quality gate) to actually fix.

**"Why isn't this agentic AI, or RAG?"**
Deliberately not agentic: this is a bounded, safety-critical task (don't
summarize a scam letter) where a fixed code path is *safer* than a model
choosing its own steps. Not RAG either: no retrieval; the photo itself is
the only grounding context, read directly via vision.

**"How would this scale to many more users?"**
Name the real limitation unprompted: the pipeline itself scales fine
(stateless, independent calls), but the 5 in-memory stores in `state.py`
don't survive a restart or work across multiple instances. The fix is an
external store like Redis, not yet built because v1 targeted a single-
instance demo, not production scale.

**"What if the model gets a figure wrong, hallucinates a CPF amount?"**
Known, named residual risk from the Haiku benchmark (one non-reproduced
numeric slip in 4 runs) — now actively mitigated by a third mechanism,
not just prompted around. Three layers: the prompt instructs hedging
("say it's unclear") over guessing when a photo is ambiguous; the summary
is a supplement to the original letter, not a replacement; and, added
25 Jul 2026, `summarize_letter_checked` reads clear-quality letters
*twice* independently and hedges any date/amount that disagrees between
the two reads rather than trusting either blindly. That closes the
specific failure mode that prompted the question (a single confidently-
wrong read going out unchallenged), but it's still not a guarantee — both
reads could coincidentally make the same misread — and I'd flag that
honestly rather than claim the risk is fully eliminated.

**"Why Haiku over Sonnet?"**
Benchmarked equivalence on the classify task (6/6 match) and near-parity
on summarize (3/4), for half the cost: a deliberate, evidence-based
choice, not an assumption that cheaper is fine.

**"How do you know this solves a real problem?"**
Cite the evidence base directly: LetterKey already proved the need (70%
of AAC seniors) and already built OCR+LLM summarization, but delivered it
as a kiosk, and their own user research showed adoption failed because of
that channel choice. Letter Kaki's entire premise is fixing that one
variable: WhatsApp instead of a kiosk.

**"What was the hardest design decision?"**
Either the scam-gate/completeness tradeoff (deliberately refusing to
summarize when uncertain, even though that's a worse user experience for
a false positive) or bilingual-by-default vs. asking (adding cost/latency
to avoid a chicken-and-egg language barrier).

**"What's not done yet?"**
Be upfront: Phase 4 (demo video + written portfolio piece) is outstanding,
timeline is tight against the 31 Jul deadline. Everything else (core
pipeline, WhatsApp integration, safety gate) is built and tested.

**"What would you change with more time?"**
Persistent state (Redis) for real multi-instance scale, a small written
eval set instead of manual notebook spot-checks, and actually going
through WhatsApp Business API verification instead of the sandbox.

**"What's your long-term vision for this, where would you take it with
more time?"**
The core insight generalizes beyond letters: WhatsApp removes the same
adoption barrier for at least two other real, already-funded senior
services: AIC/Lions Befrienders' befriending programmes and AAC activity
discovery, both of which exist today but require knowing to seek them out
via a hotline or in-person visit. I'd add those as additional intents
behind a lightweight router, always routing to the existing
service/partner rather than rebuilding it, and keeping the same
safety-gate-before-acting posture (e.g. surfacing 995/999 immediately on
anything emergency-shaped). That's real added scope, not a free
extension: PDPA implications multiply once you're forwarding stated needs
or location to a third party, so it'd need a genuine AIC/AAC partnership,
not something to self-build. See §10 for the full reasoning.
