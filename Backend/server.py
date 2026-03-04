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
    is_complete: bool = False

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
        
        # Check if we should stop probing (max 2 AI probes for this question)
        ai_probes_count = sum(1 for msg in request.chat_history if msg.role in ("ai", "AIMessage"))
        if ai_probes_count >= 2:
            return ChatResponse(
                probe="",
                safe_input=safe_input,
                is_complete=True
            )
            
        # 2. Build dynamic LLM based on request settings
        llm = ChatOpenAI(
            base_url="http://localhost:1234/v1",
            api_key="lm-studio",
            model=request.model_name,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )
        
        # 3. Build the LangChain message history
        sys_msg = (
            "You are a neutral, professional survey moderator for the Pew Research Center. "
            "Your task is to evaluate if the respondent's answer makes their overall response complete, and if not, ask exactly ONE brief, clarifying follow-up question. "
            "A complete open-ended survey or interview response provides detailed, context-rich, and relevant information in the respondent's own words, going beyond 'yes/no' to explain the why and how behind their perspective. "
            "\n\nKey Elements of a Complete Response:\n"
            "- Topical Relevance (Directness): explicitly addresses the core subject of the prompt.\n"
            "- Explanatory Depth (The 'Why'): provides the underlying rationale, containing at least one supporting reason or causal link.\n"
            "- Clarity and Unambiguity: the statement must be internally consistent.\n"
            "\nExamples of Complete Responses:\n"
            "1. [Q: Would you be comfortable with an AI tool being used to screen loan applications by banks, or not?\n"
            "A: As a software engineer, I wouldn't be comfortable with AI unilaterally screening loan applications because I know firsthand that models are only as good as their training data...]\n"
            "2. [Q: Do you think oil and gas companies should or shouldn't be held legally responsible for the costs of natural disasters linked to climate change?\n"
            "A: I absolutely believe oil and gas companies must be held legally responsible for climate-related disasters, especially since living in Seattle means watching our summers get increasingly choked by wildfire smoke...]\n\n"
            "CRITICAL RULES: \n"
            "1. You MUST respond ONLY with a valid JSON object. Do not include markdown formatting, backticks, or conversational text.\n"
            "2. The JSON object must have exactly these keys: {\"is_complete\": boolean, \"probe\": \"string\"}\n"
            "3. If is_complete is true, make the probe an empty string.\n"
            "4. Briefly and neutrally acknowledge their specific answer before asking the follow-up (e.g., 'Thank you for sharing that. You mentioned [topic]...'). Do not validate their opinion (do not say 'That's a good point'). DO NOT introduce yourself.\n"
            "5. The probe must ONLY be the acknowledgment and the question itself."
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
        
        # 4. Invoke LLM with retry loop for bias check
        max_attempts = 2
        final_probe = ""
        is_complete = False
        
        for attempt in range(max_attempts):
            print(f"Generating probe (attempt {attempt + 1}) for safe_input: '{safe_input}' using {request.model_name}")
            response = llm.invoke(messages)
            
            # Parse JSON using regex to find the first JSON object
            import re
            content = response.content.strip()
            
            # Try to extract just the JSON part if the model hallucinated extra text
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            
            try:
                if json_match:
                    json_str = json_match.group(0)
                    parsed = json.loads(json_str)
                else:
                    # Fallback if no {} found, try cleaning backticks anyway
                    clean_content = content.replace("```json", "").replace("```", "").strip()
                    parsed = json.loads(clean_content)
                    
                is_complete = parsed.get("is_complete", False)
                final_probe = parsed.get("probe", "").strip()
            except Exception as e:
                print(f"JSON parsing failed: {e}. Raw content: {content}")
                is_complete = False
                final_probe = "Could you elaborate on that?"
                
            if is_complete or not final_probe:
                is_complete = True
                final_probe = ""
                break
                
            # Bias Check
            bias_sys_msg = (
                "You are an objective bias reviewer. Analyze the following generated survey probe: \n\n"
                f"\"{final_probe}\"\n\n"
                "Does this contain leading language, bias, or assumptions? A leading question suggests a particular answer or contains the interviewer's opinion. "
                "Respond ONLY with a valid JSON object with a single boolean key: {\"is_leading\": true/false}. Do not include any other text."
            )
            bias_llm = ChatOpenAI(
                base_url="http://localhost:1234/v1",
                api_key="lm-studio",
                model=request.model_name,
                temperature=0.0,
                max_tokens=50
            )
            bias_response = bias_llm.invoke([SystemMessage(content=bias_sys_msg)])
            bias_content = bias_response.content.strip()
            
            bias_match = re.search(r'\{.*\}', bias_content, re.DOTALL)
            is_leading = False
            try:
                if bias_match:
                    bias_parsed = json.loads(bias_match.group(0))
                else:
                    clean_bias = bias_content.replace("```json", "").replace("```", "").strip()
                    bias_parsed = json.loads(clean_bias)
                is_leading = bias_parsed.get("is_leading", False)
            except:
                print(f"Bias Check JSON parsing failed. Raw: {bias_content}")
                
            if not is_leading:
                break
            else:
                print(f"Probe flagged as leading: {final_probe}")
                if attempt < max_attempts - 1:
                    messages.append(AIMessage(content=response.content))
                    messages.append(HumanMessage(content="That probe was flagged as leading or biased. Please regenerate a completely neutral clarifying question. Ensure it evaluates the user's response objectively and doesn't assume their stance, output only the JSON object."))
                else:
                    # Fallback to restating original question
                    fallback_context = request.question_context if request.question_context else "your previous statement"
                    final_probe = f"Could you elaborate on your answer regarding: '{fallback_context}'?"
                    break
        
        return ChatResponse(
            probe=final_probe,
            safe_input=safe_input,
            is_complete=is_complete
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
