from fastapi import FastAPI

app = FastAPI()


@app.post("/webhook")
async def whatsapp_webhook() -> None:
    raise NotImplementedError
