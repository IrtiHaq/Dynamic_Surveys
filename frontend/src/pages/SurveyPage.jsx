import React, { useState, useEffect } from 'react';
import { Model, Serializer } from 'survey-core';

// Register the custom property so SurveyJS parses it correctly
Serializer.addProperty("question", "pew_ai_probe:boolean");
import { Survey } from 'survey-react-ui';
import 'survey-core/survey-core.min.css';

import surveyJson from '../survey_definition.json';
import { generateProbe, getSettings, warmupModel, submitSurvey, askClarification } from '../api';

export default function SurveyPage() {
    const [surveyModel, setSurveyModel] = useState(null);
    const [clarificationState, setClarificationState] = useState({
        isOpen: false,
        message: '',
        loading: false,
        history: []
    });
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
    const [isChecking, setIsChecking] = useState(false);

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
        setIsChecking(true);
        setProbingState(prev => ({
            ...prev,
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

        if (apiResponse.is_complete) {
            // The response was complete enough! Skip probing.
            surveyInstance.setValue(question.name + '_probe_completed', true);
            setIsChecking(false);
            surveyInstance.nextPage();
            return;
        }

        setIsChecking(false);
        setProbingState(prev => ({
            ...prev,
            active: true,
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

        // Send the updated conversation back to the AI
        const apiResponse = await generateProbe(
            probingState.originalAnswer, // backend doesn't care much since chat_history has the real new reply
            newChatHistory,
            settings,
            probingState.originalQuestionTitle
        );

        if (apiResponse.is_complete) {
            // AI is satisfied or max limit hit! End the probing session.

            // Save the probing conversation into the survey data payload
            const probingDataKey = `probe_for_${probingState.originalQuestionName}`;
            surveyModel.setValue(probingDataKey, newChatHistory);

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
            return;
        }

        // Otherwise, show the user the NEXT probe and let them reply again
        setProbingState(prev => ({
            ...prev,
            loading: false,
            aiProbe: apiResponse.probe,
            userReply: '',
            chatHistory: [
                ...newChatHistory,
                { role: 'ai', content: apiResponse.probe }
            ]
        }));
    };

    const toggleClarification = () => {
        setClarificationState(prev => ({ ...prev, isOpen: !prev.isOpen }));
    };

    const handleClarificationChange = (e) => {
        setClarificationState(prev => ({ ...prev, message: e.target.value }));
    };

    const submitClarification = async (e) => {
        e.preventDefault();
        if (!clarificationState.message.trim() || clarificationState.loading) return;

        const userMsg = clarificationState.message;
        setClarificationState(prev => ({
            ...prev,
            message: '',
            loading: true,
            history: [...prev.history, { role: 'user', content: userMsg }]
        }));

        const response = await askClarification(userMsg);

        setClarificationState(prev => ({
            ...prev,
            loading: false,
            history: [...prev.history, { role: 'ai', content: response.definition }]
        }));
    };

    return (
        <div className="survey-container" style={{ position: 'relative' }}>
            {isChecking && (
                <div style={{
                    position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
                    backgroundColor: 'rgba(255,255,255,0.8)', zIndex: 10,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    flexDirection: 'column'
                }}>
                    <div className="loading-spinner" style={{ marginBottom: '1rem', border: '4px solid #f3f3f3', borderTop: '4px solid #3498db', borderRadius: '50%', width: '40px', height: '40px', animation: 'spin 1s linear infinite' }}></div>
                    <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
                    <p style={{ fontWeight: 'bold' }}>Analyzing response...</p>
                </div>
            )}
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
                        {/* Context: remind user what they just said originally */}
                        <div className="chat-message user" style={{ opacity: 0.7 }}>
                            <div className="sender">Your original answer</div>
                            <p>"{probingState.originalAnswer}"</p>
                        </div>

                        {/* Render all subsequent back-and-forth dynamically */}
                        {probingState.chatHistory.map((msg, index) => {
                            // The very first msg is just originalAnswer re-sent to AI, skip it here visually 
                            // to avoid duplicating the "Your original answer" block above.
                            if (index === 0 && msg.role === 'user') return null;

                            return (
                                <div key={index} className={`chat-message ${msg.role === 'ai' ? 'ai' : 'user'}`}>
                                    <div className="sender">
                                        {msg.role === 'ai' ? 'Survey Assistant' : 'You'}
                                    </div>
                                    <p>{msg.content}</p>
                                </div>
                            );
                        })}

                        {/* Loading State for NEXT AI Probe */}
                        {probingState.loading && (
                            <div className="loading-indicator">
                                Generating follow-up question...
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

            {/* Floating Clarification Assistant */}
            <div className="clarification-widget" style={{
                position: 'fixed',
                bottom: '20px',
                right: '20px',
                zIndex: 1000,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'flex-end'
            }}>
                {clarificationState.isOpen && (
                    <div style={{
                        width: '320px',
                        height: '420px',
                        backgroundColor: 'var(--pew-white, #fff)',
                        border: '1px solid var(--pew-gray-300, #ccc)',
                        borderRadius: '12px',
                        boxShadow: '0 8px 24px rgba(0,0,0,0.15)',
                        marginBottom: '15px',
                        display: 'flex',
                        flexDirection: 'column',
                        overflow: 'hidden'
                    }}>
                        <div style={{ backgroundColor: 'var(--pew-black, #000)', color: 'white', padding: '12px 16px', fontWeight: 'bold', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontSize: '0.95rem' }}>Ask for Clarification</span>
                            <button onClick={toggleClarification} style={{ background: 'none', border: 'none', color: 'white', cursor: 'pointer', fontSize: '1.2rem', padding: '0 5px' }}>&times;</button>
                        </div>
                        <div style={{ flex: 1, padding: '16px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                            {clarificationState.history.length === 0 && (
                                <p style={{ fontSize: '0.9rem', color: '#666', textAlign: 'center', marginTop: '30px' }}>
                                    Need help with a term like <b>Regulation</b> or <b>Bias</b> Ask the Clarification Assistant
                                </p>
                            )}
                            {clarificationState.history.map((msg, idx) => (
                                <div key={idx} style={{
                                    alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                                    backgroundColor: msg.role === 'user' ? '#e6f2ff' : '#f1f1f1',
                                    color: msg.role === 'user' ? '#004085' : '#333',
                                    padding: '10px 14px',
                                    borderRadius: '16px',
                                    borderBottomRightRadius: msg.role === 'user' ? '4px' : '16px',
                                    borderBottomLeftRadius: msg.role === 'ai' ? '4px' : '16px',
                                    maxWidth: '85%',
                                    fontSize: '0.9rem',
                                    lineHeight: '1.4'
                                }}>
                                    {/* Simple markdown-like bolding for definitions if "**Term**:" exists */}
                                    {msg.content.split('**').map((part, i) => i % 2 !== 0 ? <b key={i}>{part}</b> : part)}
                                </div>
                            ))}
                            {clarificationState.loading && (
                                <div style={{ alignSelf: 'flex-start', fontSize: '0.85rem', fontStyle: 'italic', color: '#888', padding: '5px' }}>
                                    Searching FAQ...
                                </div>
                            )}
                        </div>
                        <form onSubmit={submitClarification} style={{ display: 'flex', borderTop: '1px solid #eaeaea', backgroundColor: '#fafafa' }}>
                            <input
                                type="text"
                                value={clarificationState.message}
                                onChange={handleClarificationChange}
                                placeholder="E.g. What does API mean?"
                                style={{ flex: 1, border: 'none', padding: '14px', outline: 'none', fontSize: '0.95rem', backgroundColor: 'transparent' }}
                            />
                            <button type="submit" disabled={clarificationState.loading} style={{ background: 'none', border: 'none', padding: '0 16px', cursor: 'pointer', color: '#0066cc', fontWeight: 'bold', fontSize: '0.95rem' }}>Send</button>
                        </form>
                    </div>
                )}
                {!clarificationState.isOpen && (
                    <button onClick={toggleClarification} style={{
                        backgroundColor: 'var(--pew-black, #000)',
                        color: 'white',
                        border: 'none',
                        borderRadius: '24px',
                        padding: '12px 20px',
                        cursor: 'pointer',
                        fontWeight: '600',
                        fontSize: '0.95rem',
                        boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
                        transition: 'transform 0.2s',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px'
                    }}
                        onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-2px)'}
                        onMouseLeave={e => e.currentTarget.style.transform = 'translateY(0)'}
                    >
                        <span style={{ fontSize: '1.2rem', lineHeight: '1' }}>?</span> Ask for Clarification
                    </button>
                )}
            </div>
        </div>
    );
}
