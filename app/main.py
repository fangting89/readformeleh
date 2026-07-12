from fastapi import FastAPI

app = FastAPI()


@app.post("/webhook")
async def whatsapp_webhook() -> None:
    """Twilio WhatsApp webhook: receives a letter photo, replies with a summary."""
    raise NotImplementedError
