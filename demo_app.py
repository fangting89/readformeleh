"""Streamlit demo: shows what happens after a letter photo is sent on
WhatsApp, using the exact same pipeline the real bot runs.

Reuses pipeline.classify.classify_letter and
pipeline.summarize.summarize_letter_checked directly, no logic
duplicated. Branching mirrors pipeline/run.py's CLI exactly: suspicious
and unreadable letters are never summarized, degraded-quality photos are
never summarized either, only image_quality == "clear" letters reach
summarize_letter_checked's independent double-read.

Scoped to the 14 existing samples/*.jpg specimens only, no photo upload.
Two reasons: classify_letter + summarize_letter_checked together cost 3
Claude vision calls per analysis (vision tokens cost more than text), and
a public demo that accepted arbitrary uploads would mean strangers'
personal documents flowing through an API key this project pays for,
in tension with the product's own "nothing is stored" privacy stance.

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
]

DISCLAIMER = (
    "Independent personal portfolio project. This demo runs the real "
    "classification and summarization pipeline against pre-loaded sample "
    "letters, it does not send or receive real WhatsApp messages."
)

st.set_page_config(page_title="ReadLeh", page_icon="🙏")
st.title("ReadLeh")
st.caption(
    "See what happens after a photo of a government letter is sent on "
    "WhatsApp, using the real pipeline behind the bot."
)
st.caption(f"⚠️ {DISCLAIMER}")

with st.sidebar:
    st.header("About ReadLeh")
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
    st.caption("[Source on GitHub](https://github.com/fangting89/read-leh)")

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

if st.button("Analyze this letter", type="primary"):
    with st.spinner("Reading the letter..."):
        classify_result = classify_letter(photo_path)

    summary_en = None
    if classify_result["category"] not in ("suspicious", "unreadable") and (
        classify_result["image_quality"] == "clear"
    ):
        with st.spinner("Summarizing (reads the letter twice, independently)..."):
            summary_en = summarize_letter_checked(photo_path)

    st.session_state.analysis = {"classify": classify_result, "summary_en": summary_en}
    st.session_state.summary_zh = None

analysis = st.session_state.get("analysis")
if analysis:
    result = analysis["classify"]
    st.write(
        f"**Category:** `{result['category']}`  |  "
        f"**Photo quality:** `{result['image_quality']}`"
    )

    if result["category"] == "suspicious":
        st.error(
            "This letter looks suspicious, it won't be summarized "
            "(that could help a scammer). Red flags noticed:"
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
        lang = st.radio("Language", ["English", "中文"], horizontal=True)
        with st.container(border=True):
            if lang == "中文":
                if st.session_state.get("summary_zh") is None:
                    with st.spinner("Translating..."):
                        st.session_state.summary_zh = translate_summary(
                            analysis["summary_en"], "zh"
                        )
                st.write(st.session_state.summary_zh)
            else:
                st.write(analysis["summary_en"])
