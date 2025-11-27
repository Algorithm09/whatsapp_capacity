from fastapi import FastAPI, Request, HTTPException
import os
import requests
from pydantic import BaseModel
from huggingface_hub import InferenceClient
from langchain_core.prompts import ChatPromptTemplate


api_key = os.getenv("huggingface_api_key")
client = InferenceClient(api_key=api_key)
model = "openai/gpt-oss-20b"

app = FastAPI()

# Base prompt
template = """
You are an expert in geography, you direct people politely  using Google Maps.
You are always ready to help. 
If being asked about a location, you always provide exact address and coordinates.
"""
base_prompt = ChatPromptTemplate.from_template(template)
message_history = [{"role": "system", "content": base_prompt}]

# WhatsApp credentials
WHATSAPP_TOKEN = os.getenv("whatsapp_token")  # Access Token
PHONE_NUMBER_ID = os.getenv("phone_number_id")  # Phone number ID

# Chat function
def get_reply(user_query):
    message_history = ({"role": "user", "content": user_query})
    response = client.chat.completions.create(model=model, messages=message_history)
    reply = response.choices[0].message["content"]
    #message_history.append({"role": "assistant", "content": reply})
    return reply

# WhatsApp webhook verification
@app.get("/webhook")
def verify_webhook(request: Request):
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.challenge"):
        token = params.get("hub.verify_token")
        if token == os.getenv("whatsapp_verify_token"):
            return int(params.get("hub.challenge"))
    raise HTTPException(status_code=400, detail="Invalid verification")

# WhatsApp webhook to receive messages
@app.post("/webhook")
async def receive_message(req: Request):
    data = await req.json()
    try:
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                message_data = change["value"]["messages"][0]
                phone = message_data["from"]
                text = message_data["text"]["body"]
                
                # Get AI reply
                reply_text = get_reply(text)
                
                # Send reply back via WhatsApp Cloud API
                url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
                headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
                payload = {
                    "messaging_product": "whatsapp",
                    "to": phone,
                    "text": {"body": reply_text}
                }
                requests.post(url, headers=headers, json=payload)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
