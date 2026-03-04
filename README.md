# Dynamic Surveys: Agentic Probing Bot

A Proof of Concept (PoC) for an AI-powered survey platform designed to improve the quality of open-ended survey responses. By transforming static questionnaires into interactive conversations, this system acts as a neutral survey moderator that evaluates respondent answers in real-time and asks clarifying follow-up questions to gather rich, qualitative data.

## Key Features

* **Real-Time Agentic Probing:** Evaluates whether an open-ended response is complete (topically relevant, explanatory, and clear). If incomplete, it generates a single, context-aware follow-up question.
* **Automated Bias Checking:** Implements a secondary "LLM-as-a-judge" mechanism to scan all generated probes for leading language or assumptions, ensuring strict neutrality.
* **Dynamic Privacy Filtering (PII Redaction):** Uses Microsoft Presidio and SpaCy to instantly detect and redact Personally Identifiable Information (PII) before any data is sent to the LLM. Supports toggling between `Standard`, `HIPAA`, and `GDPR` compliance modes.
* **Survey Fatigue Guardrails:** Hard-capped at a maximum of two AI-generated probes per question to prevent frustrating the respondent.
* **Local, Privacy-First AI:** Built to run entirely locally using LM Studio and the `gemma-3n-e4b` model, ensuring no survey data is transmitted to external API providers.

## Tech Stack

**Frontend:**
* React 19 & Vite
* SurveyJS (`survey-core`, `survey-react-ui`) for dynamic survey rendering
* React Router for navigation

**Backend:**
* Python 3.12+ & FastAPI
* LangChain (adapted for local OpenAI-compatible endpoints)
* Microsoft Presidio & SpaCy (`en_core_web_sm`) for NLP-based PII redaction

**AI & Model Serving:**
* LM Studio (Local AI server)
* Target Model: `gemma-3n-e4b`

**Responsible AI Guardrails:**
This project specifically addresses the risks associated with using Generative AI in survey data collection:
* **Consent & Privacy:** Users interact with an overt AI moderator. Data is anonymized via Presidio before prompt generation.
* **Neutrality:** An LLM-as-a-judge system intercepts the primary model's output and blocks any questions that contain leading language or assumptions about the user's opinions.
* **Determinism:** The models run at a low temperature (0.1) to ensure stable, predictable logic flow rather than creative text generation.

**Core API Endpoints**
* **POST /api/chat:** Takes a user's survey response and chat history, applies PII redaction based on the requested compliance mode, and returns either a dynamic follow-up probe or a completion flag.
* **POST /api/submit:** Flattens the final survey data (including chat/probe history) and appends it to a local responses.csv file.
* **POST /api/warmup:** Pings LM Studio to load the LLM into VRAM so it is ready for the first survey respondent.

**Project Structure**
```text
├── Backend/
│   ├── server.py             # FastAPI entry point and endpoint definitions
│   └── Basic_chatbot.py      # Core LangChain logic, bias checking, and PII redaction
├── frontend/
│   ├── src/                  # React components, SurveyJS configuration, and API hooks
│   ├── package.json          # Node dependencies and Vite scripts
│   └── index.html            # Web entry point
├── Response Data/
│   └── responses.csv         # Local storage for finalized survey submissions
├── start_all.sh              # Concurrent startup script for development
└── requirements.txt          # Python environment dependencies
```
