from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
import sqlite3
import os
import asyncio
from pydantic import BaseModel
from dependencies import get_db_conn

router = APIRouter()


class ChatRequest(BaseModel):
    message: str


@router.post("/api/chat")
async def chat_ia(req: ChatRequest, db: sqlite3.Connection = Depends(get_db_conn)):
    text = req.message.lower()
    
    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            
            prompt = f"Eres un asistente técnico experto en reparación de hardware. Responde de forma concisa, profesional y da soluciones prácticas a este problema:\n\n{text}"
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt
            )
            return JSONResponse(content={"reply": response.text})
        except Exception as e:
            error_str = str(e).lower()
            if "429" in error_str or "quota" in error_str or "exhausted" in error_str:
                return JSONResponse(content={"reply": "⚠️ La Inteligencia Artificial ha superado el límite de tokens gratuitos por el momento. Por favor, inténtalo de nuevo en un par de minutos."})
            return JSONResponse(content={"reply": f"Error con la API de Gemini: {e}"})

    await asyncio.sleep(2)
    respuesta = "No encontré un procedimiento exacto en mi base de conocimientos. Recomiendo un diagnóstico físico completo."
    
    c = db.cursor()
    c.execute("SELECT * FROM knowledge_base")
    sops = c.fetchall()
    
    for sop in sops:
        keywords = [k.strip().lower() for k in sop["keywords"].split(",")]
        if any(keyword in text for keyword in keywords):
            respuesta = f"Basado en los síntomas, he consultado el SOP '{sop['title']}'. Te sugiero intentar:\n\n{sop['content']}"
            break
            
    return JSONResponse(content={"reply": f"[Modo Simulación]\n{respuesta}"})
