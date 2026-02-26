import os
from functools import lru_cache
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

# PII Redaction Setup
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

# Initialize the conversation with the strict system prompt
chat_history = [
    SystemMessage(content=(
        "Act as a neutral human survey moderator. Do not lead the respondent. "
        "Ask exactly one brief, clarifying follow-up question based on their previous text."
    ))
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
            response = llm.invoke(chat_history)
            
            # Print the AI's response
            print(f"\nSurvey Agent: {response.content}")
            
            # 4. Save AI response to memory for context
            chat_history.append(AIMessage(content=response.content))
            
        except Exception as e:
            print(f"\n[Error] Connection to LM Studio failed: {e}")
            print("Please ensure LM Studio is running and the Local Server is started.")

if __name__ == "__main__":
    main()