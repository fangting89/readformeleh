"""Static WhatsApp reply message templates.

Bilingual by default: the target audience may not read English well
enough to understand an instruction telling them how to ask for Mandarin,
so every bot-authored message shows both languages until a sender's
preference is known (see app.state.LanguagePreference)."""

ACK = "Reading your letter, one moment 🙏\n正在看您的信，请稍等 🙏"

USAGE_INSTRUCTIONS = (
    "Hi! Send a photo of a letter (CPF, IRAS, HDB, town council, a bill) "
    "and I'll explain it in plain language.\n"
    "您好！请发送信件照片（公积金、税务局、建屋局、市镇理事会账单等），"
    "我会用简单的话为您解释。"
)

SUSPICIOUS_WARNING = (
    "⚠️ This letter looks suspicious — it has signs of being a scam, so I "
    "won't summarize it (that could help the scammer). If you're not sure, "
    "call the ScamShield helpline at 1799 to check before doing anything "
    "it asks for.\n"
    "⚠️ 这封信看起来可疑，可能是诈骗信件，所以我不会为您总结内容"
    "（这样做可能会帮到骗子）。如果不确定，请拨打ScamShield防骗热线1799询问，"
    "再采取任何行动。"
)

UNREADABLE_RETRY = (
    "I couldn't read this photo clearly enough to summarize it. Could you "
    "try again with more light, holding the letter flat and the camera "
    "steady?\n"
    "这张照片不够清楚，我看不清楚内容。可以请您在光线充足的地方，"
    "把信件放平，拍一张更清楚的照片吗？"
)

UNREADABLE_RETRY_ESCALATED = (
    "This is the second photo in a row I couldn't read clearly. If it's "
    "hard to get a clear shot, it might help to ask a family member to "
    "try, or bring the letter to your nearest Active Ageing Centre — "
    "staff there can help you read it in person.\n"
    "这已经是连续第二张不够清楚的照片了。如果拍照有困难，可以请家人帮忙，"
    "或者把信件带到附近的乐龄活动中心，工作人员可以当面帮您看信。"
)

RATE_LIMITED = (
    "You've sent quite a few letters recently — please wait a bit before "
    "sending another.\n"
    "您最近发送了不少信件，请稍等一会儿再发送新的。"
)

NO_CACHED_SUMMARY = (
    "I don't have a recent summary to translate — please send the letter "
    "photo again.\n"
    "我没有最近的摘要可以翻译，请重新发送信件照片。"
)

PROCESSING_ERROR = (
    "Sorry, something went wrong on my end. Please try sending the letter "
    "again.\n"
    "抱歉，我这边出了一些问题。请重新发送信件。"
)

CHINESE_KEYWORDS = {"中文", "zh", "chinese", "mandarin"}
ENGLISH_KEYWORDS = {"english", "en"}


def bilingual_summary(english: str, chinese: str) -> str:
    """Combines an English and Mandarin summary into one bilingual reply."""
    return f"{english}\n\n———\n\n{chinese}"
