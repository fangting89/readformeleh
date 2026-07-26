# read-leh

A WhatsApp-native bot that summarizes official government letters (CPF,
IRAS, HDB, town council) into plain-language English/Mandarin, for
Singaporean seniors and their caregivers. Includes a scam-detection safety
layer that withholds a summary and refers to ScamShield instead of
summarizing suspicious mail, hardened against prompt-injection attempts
embedded in the letter photo itself, and a self-consistency check that
re-reads a letter's key figures independently before trusting them.

**Live demo:** [read-leh.streamlit.app](https://read-leh.streamlit.app)
(runs the real pipeline against pre-loaded sample letters, doesn't send or
receive real WhatsApp messages, see [Demo](#demo) below)
**Interactive walkthrough** (how the pipeline works, no live API calls needed to view): [fangting89.github.io/read-leh/walkthrough.html](https://fangting89.github.io/read-leh/walkthrough.html)

![ReadLeh demo, showing a sample letter, its classification, and the bilingual summary](docs/screenshot.png)

See [docs/DESIGN.md](docs/DESIGN.md) for the problem statement, evidence
base, architecture, and design decisions.

## Setup

```
uv sync
cp .env.example .env  # fill in ANTHROPIC_API_KEY, TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN
uvx pre-commit install
```

## Usage

```
python -m pipeline.run photo.jpg --lang zh
```

## Demo

`demo_app.py` is a Streamlit demo (not the production WhatsApp bot) that
runs the real `classify_letter` and `summarize_letter_checked` pipeline
live against the sample letters in `samples/`, no mocked output. Scoped to
those pre-loaded samples only, not arbitrary photo uploads, since each
run costs real Claude vision calls and a public upload form would mean
strangers' documents flowing through a personal API key.

```
uv run streamlit run demo_app.py
```
