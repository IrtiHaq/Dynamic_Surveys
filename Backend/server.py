from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import sys
import csv
import json
from datetime import datetime

# Define expected request and response formats
class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    compliance_mode: str = "Standard"
    chat_history: List[ChatMessage] = []
    model_name: str = "gemma-3n-e4b"
    temperature: float = 0.1
    max_tokens: int = 150
    question_context: str = ""

class ChatResponse(BaseModel):
    probe: str
    safe_input: str

class SurveySubmission(BaseModel):
    data: Dict[str, Any]

# Import the existing functionality from Basic_chatbot.py
try:
    from Basic_chatbot import anonymize_text
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
except ImportError:
    print("Error importing Basic_chatbot. Make sure you run this script from the Backend directory.")
    sys.exit(1)

app = FastAPI(title="Pew Research - Dynamic Survey API")

# Enable CORS for the local React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/chat", response_model=ChatResponse)
async def generate_probe(request: ChatRequest):
    """
    Takes a user response and chat history, applies privacy filters, 
    and generates a single clarifying follow-up probe.
    """
    try:
        # 1. Anonymize user input according to compliance mode
        safe_input = anonymize_text(request.message, compliance_mode=request.compliance_mode)
        
        # 2. Build dynamic LLM based on request settings
        llm = ChatOpenAI(
            base_url="http://localhost:1234/v1",
            api_key="lm-studio",
            model=request.model_name,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        # 3. Build the LangChain message history
        # Always start with the system prompt, including the question context if available
        sys_msg = (
            "You are a neutral, professional survey moderator for the Pew Research Center. "
            "Your ONLY task is to ask exactly ONE brief, clarifying follow-up question based on the respondent's answer. "
            "CRITICAL RULES: \n"
            "1. NEVER say 'Okay, I understand' or 'Please provide the text'.\n"
            "2. DO NOT introduce yourself or say hello.\n"
            "3. DO NOT validate their opinion (do not say 'That's interesting' or 'I see').\n"
            "4. Your response must ONLY be the question itself. The next user message you receive IS their answer, respond immediately with the probe."
        )
        if request.question_context:
            sys_msg += f"\n\nContext: The original survey question was: '{request.question_context}'"
            
        messages = [SystemMessage(content=sys_msg)]
        
        # Append prior chat history if any exists (e.g. if we allowed multi-turn probing)
        for msg in request.chat_history:
            if msg.role == "user" or msg.role == "HumanMessage":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "ai" or msg.role == "AIMessage":
                messages.append(AIMessage(content=msg.content))
                
        # Append the current safe user message
        messages.append(HumanMessage(content=safe_input))
        
        # 4. Invoke LLM
        print(f"Generating probe for safe_input: '{safe_input}' using {request.model_name}")
        response = llm.invoke(messages)
        
        return ChatResponse(
            probe=response.content,
            safe_input=safe_input
        )
        
    except Exception as e:
        print(f"Error communicating with LLM: {str(e)}")
        raise HTTPException(status_code=500, detail=f"LLM Connection Error: {str(e)}")

# Placeholder for settings API if we want to save them to backend later
@app.get("/api/settings")
async def get_settings():
    return {"status": "ok", "message": "Settings saved in browser localStorage for PoC"}

@app.post("/api/warmup")
async def warmup_model():
    """Sends a tiny request to LM Studio to load the model into VRAM so it's ready."""
    try:
        print("Pre-warming LM Studio model...")
        # Since we decoupled, we just build a generic Chat OpenAI to hit the endpoint
        from langchain_openai import ChatOpenAI
        warmup_llm = ChatOpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio", max_tokens=1)
        warmup_llm.invoke([SystemMessage(content="Respond with 'OK'")])
        return {"status": "warmed_up"}
    except Exception as e:
        print(f"Warmup failed: {e}")
        return {"status": "failed", "error": str(e)}

@app.post("/api/submit")
async def submit_survey(submission: SurveySubmission):
    try:
        # Define the path to save data outside the Backend folder
        csv_path = os.path.join(os.path.dirname(__file__), "..", "Response Data", "responses.csv")
        os.makedirs(os.path.dirname(csv_path), exist_ok=True)
        
        # Flatten the data (e.g., stringify list objects like probe history)
        flat_data = {}
        for k, v in submission.data.items():
            if isinstance(v, (list, dict)):
                flat_data[k] = json.dumps(v)
            else:
                flat_data[k] = v
        flat_data['timestamp'] = datetime.now().isoformat()
        
        file_exists = os.path.exists(csv_path)
        with open(csv_path, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=flat_data.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(flat_data)
            
        print(f"Saved response to {csv_path}")
        return {"status": "success"}
    except Exception as e:
        print(f"Failed to save response: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Pre-warm models via Basic_chatbot hook
    print("Starting API Server. Pre-warming privacy rules...")
    from Basic_chatbot import load_presidio_engines
    load_presidio_engines()
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
