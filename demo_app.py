"""Streamlit demo: shows what happens after a letter photo is sent on
WhatsApp, using the exact same pipeline the real bot runs.

Reuses pipeline.classify.classify_letter and
pipeline.summarize.summarize_letter_checked directly, no logic
duplicated. Branching mirrors pipeline/run.py's CLI exactly: suspicious
and unreadable letters are never summarized, degraded-quality photos are
never summarized either, only image_quality == "clear" letters reach
summarize_letter_checked's independent double-read.

Scoped to the pre-generated samples/*.jpg specimens only, no photo upload.
Two reasons: classify_letter + summarize_letter_checked together cost 3
Claude vision calls per analysis (vision tokens cost more than text), and
a public demo that accepted arbitrary uploads would mean strangers'
personal documents flowing through an API key this project pays for,
in tension with the product's own "nothing is stored" privacy stance.

Also rate-capped per session (MAX_ANALYSES_PER_SESSION below) as a second,
independent cost/abuse control - deliberately scoped to per-session, not a
persisted daily cap: a static Streamlit Community Cloud demo has no shared
database to count against across sessions/restarts without adding real
infra for a portfolio demo, so a session-local counter is the honest,
achievable version of this control (see the README's Scalability section
for what a real production rate limit would need instead).

samples/*.jpg are gitignored (samples/README.md's policy: never commit a
real letter), and these are 100% synthetic specimens, so that policy
isn't really about them, but regenerating from source on first run
(scripts/generate_samples.py, deterministic from eval/dataset.py) is
cleaner than carving out a gitignore exception, and means a fresh clone
(e.g. Streamlit Community Cloud) works without the binary images ever
being committed.

Run with: uv run streamlit run demo_app.py
"""

from pathlib import Path

import streamlit as st

from pipeline.classify import classify_letter
from pipeline.summarize import summarize_letter_checked, translate_summary
from scripts.generate_samples import main as generate_samples

SAMPLES_DIR = Path(__file__).resolve().parent / "samples"

MAX_ANALYSES_PER_SESSION = 15


@st.cache_resource
def _ensure_samples_exist() -> None:
    """Regenerates samples/*.jpg from source if they're missing (e.g. a
    fresh clone, where they're gitignored). Cached so this only runs once
    per app process, not on every rerun."""
    if not any(SAMPLES_DIR.glob("*.jpg")):
        generate_samples()


_ensure_samples_exist()

SAMPLE_LETTERS = [
    ("CPF Statement (genuine)", "cpf_statement.jpg"),
    ("HDB Notice (genuine)", "hdb_notice.jpg"),
    ("IRAS Notice (genuine)", "iras_notice.jpg"),
    ("Town Council Notice (genuine)", "town_council_notice.jpg"),
    ("Dental Clinic Bill (genuine)", "dental_clinic_bill.jpg"),
    ("Polyclinic Bill (genuine)", "polyclinic_bill.jpg"),
    ("Bad Quality Photo (unreadable test)", "bad_quality_photo.jpg"),
    ("Heavy Blur (degraded-photo test)", "heavy_blur_notice.jpg"),
    ("Low Light (degraded-photo test)", "low_light_notice.jpg"),
    ("Partial Crop (degraded-photo test)", "partial_crop_notice.jpg"),
    ("Scam Letter (suspicious test)", "scam_letter.jpg"),
    ("Fake Bank OTP Scam (suspicious test)", "scam_bank_otp.jpg"),
    ("Fake Police Scam (suspicious test)", "scam_spf_impersonation.jpg"),
    ("Prompt-Injection Scam (suspicious test)", "scam_prompt_injection.jpg"),
    ("Lucky Draw Prize Scam (suspicious test)", "scam_prize.jpg"),
    ("Romance Scam (suspicious test)", "scam_romance.jpg"),
    ("Guaranteed-Returns Investment Scam (suspicious test)", "scam_investment.jpg"),
    (
        "Fake Police Warrant Scam, real advisory (suspicious test)",
        "scam_real_police_warrant.jpg",
    ),
    ("Fake PDPC Officer Scam, real advisory (suspicious test)", "scam_real_pdpc.jpg"),
]

DISCLAIMER = (
    "Independent personal portfolio project. This demo runs the real "
    "classification and summarization pipeline against pre-loaded sample "
    "letters, it does not send or receive real WhatsApp messages."
)

st.set_page_config(page_title="ReadForMeLeh", page_icon="🙏")
st.title("Government Letter Summarizer & Scam Detector")
st.caption("readformeleh")
st.caption(
    "See what happens after a photo of a government letter is sent on "
    "WhatsApp, using the real pipeline behind the bot."
)
st.caption(f"⚠️ {DISCLAIMER}")

with st.sidebar:
    st.header("About ReadForMeLeh")
    st.write(
        "A WhatsApp bot that explains official letters (CPF, IRAS, HDB, "
        "town council) in plain language, with a scam-detection safety "
        "gate that withholds a summary rather than ever explaining a "
        "scam letter."
    )
    st.subheader("What this demo shows")
    st.write(
        "Pick a sample letter below. The same `classify_letter` and "
        "`summarize_letter_checked` functions the real bot calls run "
        "live against it, no mocked output."
    )
    st.divider()
    st.caption(DISCLAIMER)
    st.caption("[Source on GitHub](https://github.com/fangting89/readformeleh)")

label_to_filename = dict(SAMPLE_LETTERS)
chosen_label = st.selectbox("Choose a sample letter", list(label_to_filename))
photo_path = SAMPLES_DIR / label_to_filename[chosen_label]

st.image(str(photo_path), width=320)

# A language-toggle radio needs to keep showing the already-computed
# result across reruns it triggers itself, so the classify/summarize
# calls are cached in session_state on button click, not recomputed on
# every rerun (which st.button's bare return value would otherwise force,
# since it's only True on the exact click that triggered the rerun).
if str(photo_path) != st.session_state.get("photo_path"):
    st.session_state.photo_path = str(photo_path)
    st.session_state.analysis = None

analyses_used = st.session_state.get("analysis_count", 0)
if analyses_used >= MAX_ANALYSES_PER_SESSION:
    st.button("Analyze this letter", type="primary", disabled=True)
    st.caption(
        f"⚠️ This demo caps analyses at {MAX_ANALYSES_PER_SESSION} per session "
        "to control API cost (each analysis costs real Claude vision calls). "
        "Refresh the page to reset."
    )
elif st.button("Analyze this letter", type="primary"):
    st.session_state.analysis_count = analyses_used + 1
    with st.spinner("Reading the letter..."):
        classify_result = classify_letter(photo_path)

    summary_en = None
    if classify_result["category"] not in ("suspicious", "unreadable") and (
        classify_result["image_quality"] == "clear"
    ):
        with st.spinner("Summarizing (reads the letter twice, independently)..."):
            summary_en = summarize_letter_checked(photo_path)

    st.session_state.analysis = {"classify": classify_result, "summary_en": summary_en}
    for lang_code in ("zh", "ms", "ta"):
        st.session_state[f"summary_{lang_code}"] = None

analysis = st.session_state.get("analysis")
if analysis:
    result = analysis["classify"]
    st.write(
        f"**Category:** `{result['category']}`  |  "
        f"**Photo quality:** `{result['image_quality']}`"
    )

    if result["category"] == "suspicious":
        st.error(
            f"This letter looks suspicious (scam type: `{result['scam_type']}`), "
            "it won't be summarized (that could help a scammer). Red flags noticed:"
        )
        for flag in result["red_flags"]:
            st.markdown(f"- {flag}")
    elif result["category"] == "unreadable":
        st.warning(
            "Couldn't read this photo clearly enough to summarize it. "
            "In the real bot, this would prompt a retry with better "
            "lighting."
        )
    elif result["image_quality"] == "degraded":
        st.warning(
            f"Category looks like `{result['category']}`, but the photo "
            "is too degraded to safely read specific figures like dates "
            "or dollar amounts. Summarizing is skipped entirely rather "
            "than risk a wrong figure, this is a structural gate, not "
            "something the model can talk its way past."
        )
    else:
        language_options = {
            "English": "en",
            "中文": "zh",
            "Bahasa Melayu": "ms",
            "தமிழ்": "ta",
        }
        lang_label = st.radio("Language", list(language_options), horizontal=True)
        target_lang = language_options[lang_label]
        with st.container(border=True):
            if target_lang == "en":
                st.write(analysis["summary_en"])
            else:
                cache_key = f"summary_{target_lang}"
                if st.session_state.get(cache_key) is None:
                    with st.spinner("Translating..."):
                        st.session_state[cache_key] = translate_summary(
                            analysis["summary_en"], target_lang
                        )
                st.write(st.session_state[cache_key])
