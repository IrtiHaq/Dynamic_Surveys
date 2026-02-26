// API Helpers

const API_BASE_URL = 'http://localhost:8000/api';

/**
 * Sends a message to the backend LLM wrapper to get a generated follow-up probe.
 */
export async function generateProbe(message, chatHistory = [], settings = {}, questionContext = '') {
    try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message,
                compliance_mode: settings.complianceMode || 'Standard',
                model_name: settings.modelName || 'gemma-3n-e4b',
                temperature: parseFloat(settings.temperature) || 0.1,
                max_tokens: parseInt(settings.maxTokens) || 150,
                question_context: questionContext,
                chat_history: chatHistory
            }),
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error generating probe:", error);
        // Return fallback for demo purposes if backend fails
        return {
            probe: "That's interesting. Could you expand a bit more on why you feel that way?",
            safe_input: message
        };
    }
}

/**
 * Pre-warm the local LLM model so the user doesn't wait long for the first probe.
 */
export async function warmupModel() {
    try {
        fetch(`${API_BASE_URL}/warmup`, { method: 'POST' }).catch(() => { });
    } catch (err) {
        // silently fail
    }
}

/**
 * Save the survey responses and probe history to the backend.
 */
export async function submitSurvey(data) {
    try {
        await fetch(`${API_BASE_URL}/submit`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ data }),
        });
    } catch (error) {
        console.error("Error submitting survey:", error);
    }
}

/**
 * Persists Survey Team Settings
 */
export function getSettings() {
    const defaultSettings = {
        enableProbing: true,
        complianceMode: 'Standard',
        modelName: 'gemma-3n-e4b',
        temperature: 0.1,
        maxTokens: 150
    };

    const saved = localStorage.getItem('pew_survey_settings');
    return saved ? { ...defaultSettings, ...JSON.parse(saved) } : defaultSettings;
}

export function saveSettings(settings) {
    localStorage.setItem('pew_survey_settings', JSON.stringify(settings));
}
