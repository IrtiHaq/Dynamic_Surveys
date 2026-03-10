import os
import json
from functools import lru_cache
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
import csv

# PII Redaction Setup
from functools import lru_cache

@lru_cache(maxsize=1)
def load_local_embeddings():
    from sentence_transformers import SentenceTransformer
    print("Loading Local Embedding Model... (This only happens once)")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    return model

@lru_cache(maxsize=1)
def build_questions_index():
    print("Building Question Embeddings Index...")
    model = load_local_embeddings()
    csv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "survey_questions.csv")
    questions = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                q_text = row.get('Question Text')
                if q_text:
                    questions.append(q_text)
        if questions:
            embeddings = model.encode(questions, convert_to_tensor=False)
            return questions, embeddings
        return [], []
    except Exception as e:
        print(f"Error loading survey_questions.csv: {e}")
        return [], []

from functools import lru_cache

# PII Redaction 
@lru_cache(maxsize=1)
def load_presidio_engines():
    """Loads Presidio once and caches it in memory for instant reuse."""
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    from presidio_anonymizer import AnonymizerEngine
    
    print("Loading NLP Privacy Filters... (This only happens once)")
    configuration = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
    }
    
    provider = NlpEngineProvider(nlp_configuration=configuration)
    analyzer = AnalyzerEngine(
        nlp_engine=provider.create_engine(), 
        supported_languages=["en"]
    )
    anonymizer = AnonymizerEngine()
    
    return analyzer, anonymizer

def anonymize_text(text: str, compliance_mode: str = "Standard") -> str:
    """
    Instantly redacts PII using cached engines based on the selected compliance framework.
    Modes: 'Standard', 'HIPAA', or 'GDPR'
    """
    if not text:
        return ""
        
    analyzer, anonymizer = load_presidio_engines()
    
    # 1. Define the baseline entities we always want to catch
    base_entities = [
        "PERSON", 
        "EMAIL_ADDRESS", 
        "PHONE_NUMBER", 
        "CREDIT_CARD", 
        "US_SSN",
        "US_BANK_NUMBER",
        "CRYPTO",
        "IBAN_CODE"
        ]
    
    # Add specific entities based on the strictness of the framework
    if compliance_mode.upper() == "HIPAA":
        # HIPAA Safe Harbor requires removing dates, geographic locations, and network IDs [cite: 12]
        entities_to_find = base_entities + ["DATE_TIME", "IP_ADDRESS", "URL"]
        
    elif compliance_mode.upper() == "GDPR":
        # GDPR broadly protects indirect identifiers like IPs and location data [cite: 12, 69]
        entities_to_find = base_entities + ["IP_ADDRESS"]
        
    else:
        # Standard mode
        entities_to_find = base_entities
        
    # Tell the analyzer exactly what to hunt for
    results = analyzer.analyze(
        text=text, 
        language="en", 
        entities=entities_to_find
    )
    
    # Redact
    anonymized_result = anonymizer.anonymize(text=text, analyzer_results=results)
    
    return anonymized_result.text

# LM Studio / LangChain Setup
# Point LangChain to LM Studio's local server port
llm = ChatOpenAI(
    base_url="http://localhost:1234/v1",
    api_key="lm-studio", # API key is required by the library, but LM Studio ignores it
    model="gemma-3n-e4b", 
    temperature=0.1,     # Low temperature for deterministic, neutral responses
    max_tokens=150
)

sys_msg = (
    "You are a neutral, professional survey moderator for the Pew Research Center. "
    "Your task is to evaluate if the respondent's answer makes their overall response complete, and if not, ask exactly ONE brief, clarifying follow-up question. "
    "A complete open-ended survey or interview response provides detailed, context-rich, and relevant information in the respondent's own words, going beyond 'yes/no' to explain the why and how behind their perspective. "
    "\n\nKey Elements of a Complete Response:\n"
    "- Topical Relevance (Directness): explicitly addresses the core subject of the prompt.\n"
    "- Explanatory Depth (The 'Why'): provides the underlying rationale, containing at least one supporting reason or causal link.\n"
    "- Clarity and Unambiguity: the statement must be internally consistent.\n"
    "\nCRITICAL RULE FOR FOLLOW-UP ANSWERS:\n"
    "- If the user has already been asked a follow-up question and their reply directly addresses that follow-up (e.g. they stated which specific jobs they mean, or provided a short reason), you MUST classify the response as complete (`is_complete: true`). Do NOT ask a second follow-up question unless their reply is complete gibberish or extremely evasive.\n"
    "\nExamples of Complete Responses:\n"
    "1. [Q: Would you be comfortable with an AI tool being used to screen loan applications by banks, or not?\n"
    "A: As a software engineer, I wouldn't be comfortable with AI unilaterally screening loan applications because I know firsthand that models are only as good as their training data...]\n"
    "2. [Q: Do you think oil and gas companies should or shouldn't be held legally responsible for the costs of natural disasters linked to climate change?\n"
    "A: I absolutely believe oil and gas companies must be held legally responsible for climate-related disasters, especially since living in Seattle means watching our summers get increasingly choked by wildfire smoke...]\n"
    "3. [Q: What concerns you most about technology in the next 5 years?\n"
    "A: It will take away jobs.\n"
    "AI: Thank you. Which types of jobs are you most concerned about and why?\n"
    "A: It will automate and take away factory jobs.\n"
    "AI (INTERNAL LOGIC): The user provided a specific example of jobs. It is complete.]\n\n"
    "CRITICAL RULES: \n"
    "1. You MUST respond ONLY with a valid JSON object. Do not include markdown formatting, backticks, or conversational text.\n"
    "2. The JSON object must have exactly these keys: {\"is_complete\": boolean, \"probe\": \"string\"}\n"
    "3. If is_complete is true, make the probe an empty string.\n"
    "4. If and only if is_complete is false, briefly and neutrally acknowledge their specific answer before asking the follow-up (e.g., 'Thank you for sharing that. You mentioned [topic]...'). Do not validate their opinion (do not say 'That's a good point'). DO NOT introduce yourself.\n"
    "5. The probe must ONLY be the acknowledgment and the question itself."
)

chat_history = [
    SystemMessage(content=sys_msg)
]

def main():
    print("\n" + "="*50)
    print("Agentic Probing Bot - Local Testing Mode")
    print("Type 'quit' or 'exit' to stop.")
    print("="*50 + "\n")
    
    # Pre-warm the cache before the user types anything
    load_presidio_engines()
    
    while True:
        user_input = input("\nRespondent: ")
        
        if user_input.lower() in ['quit', 'exit']:
            print("Ending session.")
            break
            
        # Check max probes
        ai_probes_count = sum(1 for msg in chat_history if msg.type == "ai")
        if ai_probes_count >= 2:
            print("\n[System: Max probes reached. Marking as complete.]")
            print("Survey Agent: Thank you for your response.")
            # For local test, just break and exit
            break
            
        # 1. Intercept and Anonymize
        safe_input = anonymize_text(user_input, compliance_mode="GDPR")
        
        # Show what the LLM is actually seeing for debugging
        if safe_input != user_input:
            print(f"[Privacy Filter Active] -> Sending to LLM: {safe_input}")
            
        # 2. Append to memory
        chat_history.append(HumanMessage(content=safe_input))
        
        # 3. Generate Response via LM Studio
        try:
            print("\nGenerating probe...")
            max_attempts = 2
            final_probe = ""
            is_complete = False
            
            for attempt in range(max_attempts):
                import re
                response = llm.invoke(chat_history)
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
                    model="gemma-3n-e4b",
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
                    pass
                    
                if not is_leading:
                    break
                else:
                    print(f"[System: Probe flagged as leading: {final_probe}]")
                    if attempt < max_attempts - 1:
                        chat_history.append(AIMessage(content=response.content))
                        chat_history.append(HumanMessage(content="That probe was flagged as leading or biased. Please regenerate a completely neutral clarifying question. output only the JSON object."))
                    else:
                        final_probe = "Could you elaborate on your answer regarding your previous statement?"
                        break
                        
            if is_complete:
                print("\n[System: Response mapped as complete.]")
                print("Survey Agent: Thank you for your full response.")
                break
            else:
                print(f"\nSurvey Agent: {final_probe}")
                valid_json = json.dumps({"is_complete": False, "probe": final_probe})
                chat_history.append(AIMessage(content=valid_json))
                
        except Exception as e:
            print(f"\n[Error] Connection to LM Studio failed: {e}")
            print("Please ensure LM Studio is running and the Local Server is started.")
            break

if __name__ == "__main__":
    main()