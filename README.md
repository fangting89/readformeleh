# letter-kaki

A WhatsApp-native bot that summarizes official government letters (CPF,
IRAS, HDB, town council) into plain-language English/Mandarin, for
Singaporean seniors and their caregivers. Includes a scam-detection safety
layer that withholds a summary and refers to ScamShield instead of
summarizing suspicious mail, hardened against prompt-injection attempts
embedded in the letter photo itself, and a self-consistency check that
re-reads a letter's key figures independently before trusting them.

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
