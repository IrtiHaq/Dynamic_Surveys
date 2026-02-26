import React, { useState, useEffect } from 'react';
import { Model, Serializer } from 'survey-core';

// Register the custom property so SurveyJS parses it correctly
Serializer.addProperty("question", "pew_ai_probe:boolean");
import { Survey } from 'survey-react-ui';
import 'survey-core/survey-core.min.css';

import surveyJson from '../survey_definition.json';
import { generateProbe, getSettings, warmupModel, submitSurvey } from '../api';

export default function SurveyPage() {
    const [surveyModel, setSurveyModel] = useState(null);
    const [probingState, setProbingState] = useState({
        active: false,
        originalQuestionTitle: '',
        originalQuestionName: '',
        originalAnswer: '',
        aiProbe: '',
        userReply: '',
        loading: false,
        chatHistory: [],
        pageIdToReturnTo: null
    });

    const settings = getSettings();

    useEffect(() => {
        // Pre-warm the LLM so it's ready when the user gets to the open responses
        if (settings.enableProbing) {
            warmupModel();
        }

        // Prevent Survey JS from applying its own colors wildly by using modern setup
        const survey = new Model(surveyJson);
        survey.applyTheme({
            cssVariables: {
                "--sjs-general-backcolor": "var(--pew-white)",
                "--sjs-general-hovercolor": "var(--pew-gray-200)",
                "--sjs-general-dimmed-light-color": "var(--pew-gray-100)",
                "--sjs-font-family": "Inter, sans-serif",
                "--sjs-primary-backcolor": "var(--pew-black)",
                "--sjs-primary-backcolor-light": "var(--pew-gray-800)",
                "--sjs-primary-backcolor-dark": "var(--pew-black)",
                "--sjs-border-light": "var(--pew-gray-300)",
                "--sjs-border-default": "var(--pew-gray-600)"
            }
        });

        survey.onCurrentPageChanging.add((sender, options) => {
            // If we are moving forward, check if we need to probe
            if (options.isNextPage && settings.enableProbing) {
                const currentPage = sender.currentPage;
                let requiresProbing = false;
                let targetQuestion = null;

                // Find if any question on this page wants an AI probe
                currentPage.questions.forEach(q => {
                    const hasProbe = q.pew_ai_probe === true || (q.jsonObj && q.jsonObj.pew_ai_probe === true);
                    const probeCompleted = sender.getValue(q.name + '_probe_completed');
                    if (hasProbe && q.value && !probeCompleted) {
                        requiresProbing = true;
                        targetQuestion = q;
                    }
                });

                if (requiresProbing) {
                    // Prevent default navigation
                    options.allowChanging = false;

                    // Trigger the AI probe mode
                    startProbing(targetQuestion, sender);
                }
            }
        });

        survey.onComplete.add((sender) => {
            console.log("Survey completed. Data: ", sender.data);
            // Save responses as CSV through the backend
            submitSurvey(sender.data);
        });

        setSurveyModel(survey);
    }, [settings.enableProbing]);

    const startProbing = async (question, surveyInstance) => {
        setProbingState(prev => ({
            ...prev,
            active: true,
            loading: true,
            originalQuestionTitle: question.title,
            originalQuestionName: question.name,
            originalAnswer: question.value,
            pageIdToReturnTo: surveyInstance.currentPage.name
        }));

        // First initial human message to the AI
        const apiResponse = await generateProbe(
            question.value,
            [],
            settings,
            question.title
        );

        setProbingState(prev => ({
            ...prev,
            loading: false,
            aiProbe: apiResponse.probe,
            chatHistory: [
                { role: 'user', content: apiResponse.safe_input || question.value },
                { role: 'ai', content: apiResponse.probe }
            ]
        }));
    };

    const handleReplyChange = (e) => {
        setProbingState(prev => ({ ...prev, userReply: e.target.value }));
    };

    const submitReply = async () => {
        if (!probingState.userReply.trim()) return;

        setProbingState(prev => ({ ...prev, loading: true }));

        // Append user reply to chat history tracking
        const newChatHistory = [
            ...probingState.chatHistory,
            { role: 'user', content: probingState.userReply }
        ];

        // For this POC, we just do 1 single follow-up probe and then continue the survey immediately.
        // So we append the reply to the survey data, hide probing, and move to next page.

        // Save the probing conversation into the survey data payload
        const finalConversation = [...newChatHistory];
        const probingDataKey = `probe_for_${probingState.originalQuestionName}`;
        surveyModel.setValue(probingDataKey, finalConversation);

        // Mark this question as specifically probed so we don't infinite-loop on this page
        surveyModel.setValue(probingState.originalQuestionName + '_probe_completed', true);

        setProbingState(prev => ({
            ...prev,
            active: false,
            loading: false,
            aiProbe: '',
            userReply: '',
            chatHistory: []
        }));

        // Force navigation to the next page now that probing is done
        surveyModel.nextPage();
    };

    return (
        <div className="survey-container">
            {!probingState.active ? (
                surveyModel && <Survey model={surveyModel} />
            ) : (
                <div className="ai-probing-container">
                    <div className="ai-header">
                        <h2>
                            AI Follow-up
                            <span className="ai-badge">Moderator</span>
                        </h2>
                        <p className="text-muted" style={{ margin: 0, fontSize: '0.875rem' }}>Just one quick question...</p>
                    </div>

                    <div className="chat-history">
                        {/* Context: remind user what they just said */}
                        <div className="chat-message user" style={{ opacity: 0.7 }}>
                            <div className="sender">Your previous answer</div>
                            <p>"{probingState.originalAnswer}"</p>
                        </div>

                        {/* AI Probe */}
                        {probingState.loading && !probingState.aiProbe ? (
                            <div className="loading-indicator">
                                Generating follow-up question...
                            </div>
                        ) : (
                            <div className="chat-message ai">
                                <div className="sender">Survey Assistant</div>
                                <p>{probingState.aiProbe}</p>
                            </div>
                        )}
                    </div>

                    {!probingState.loading && (
                        <div className="reply-container">
                            <label htmlFor="ai-reply">Your response:</label>
                            <textarea
                                id="ai-reply"
                                rows="4"
                                placeholder="Type your reply here..."
                                value={probingState.userReply}
                                onChange={handleReplyChange}
                                autoFocus
                            />
                            <div className="button-group">
                                <button
                                    className="btn-primary"
                                    onClick={submitReply}
                                    disabled={!probingState.userReply.trim()}
                                >
                                    Continue Survey
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
