import React, { useState, useEffect } from 'react';
import { getSettings, saveSettings } from '../api';

export default function AdminPage() {
    const [settings, setSettings] = useState({
        enableProbing: true,
        complianceMode: 'Standard',
        modelName: 'gemma-3n-e4b',
        temperature: 0.1,
        maxTokens: 150
    });

    const [saveStatus, setSaveStatus] = useState('');

    useEffect(() => {
        setSettings(getSettings());
    }, []);

    const handleChange = (e) => {
        const { name, value, type, checked } = e.target;
        setSettings(prev => ({
            ...prev,
            [name]: type === 'checkbox' ? checked : value
        }));
    };

    const handleSave = (e) => {
        e.preventDefault();
        saveSettings(settings);
        setSaveStatus('Settings saved successfully!');
        setTimeout(() => setSaveStatus(''), 3000);
    };

    return (
        <div className="admin-panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
                <h1 style={{ margin: 0 }}>Survey Team Settings</h1>
                {saveStatus && <span style={{ color: '#2ecc71', fontWeight: 500 }}>{saveStatus}</span>}
            </div>

            <form onSubmit={handleSave}>
                <div className="admin-section">
                    <h2>Feature Controls</h2>
                    <div className="form-group">
                        <label className="radio-label" style={{ fontSize: '1.1rem' }}>
                            <input
                                type="checkbox"
                                name="enableProbing"
                                checked={settings.enableProbing}
                                onChange={handleChange}
                                style={{ width: '1.25rem', height: '1.25rem' }}
                            />
                            Enable Agentic Probing Globally
                        </label>
                        <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', marginTop: '0.5rem', marginLeft: '1.75rem' }}>
                            If disabled, the survey will function like a traditional static instrument.
                        </p>
                    </div>
                </div>

                <div className="admin-section">
                    <h2>Privacy & Compliance</h2>
                    <p style={{ color: 'var(--color-text-muted)', fontSize: '0.875rem', marginBottom: '1rem' }}>
                        Select the PII redaction strictness level applied before responses are sent to the LLM.
                    </p>
                    <div className="radio-group">
                        <label className="radio-label">
                            <input
                                type="radio"
                                name="complianceMode"
                                value="Standard"
                                checked={settings.complianceMode === 'Standard'}
                                onChange={handleChange}
                            />
                            Standard (Names, Emails, Phones)
                        </label>
                        <label className="radio-label">
                            <input
                                type="radio"
                                name="complianceMode"
                                value="GDPR"
                                checked={settings.complianceMode === 'GDPR'}
                                onChange={handleChange}
                            />
                            GDPR (Standard + IP Addresses)
                        </label>
                        <label className="radio-label">
                            <input
                                type="radio"
                                name="complianceMode"
                                value="HIPAA"
                                checked={settings.complianceMode === 'HIPAA'}
                                onChange={handleChange}
                            />
                            HIPAA Safe Harbor (GDPR + Dates, URLs)
                        </label>
                    </div>
                </div>

                <div className="admin-section">
                    <h2>LLM Configuration (LM Studio Integration)</h2>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                        <div className="form-group">
                            <label>Model Name</label>
                            <input
                                type="text"
                                name="modelName"
                                className="form-control"
                                value={settings.modelName}
                                onChange={handleChange}
                            />
                            <small style={{ color: 'var(--color-text-muted)' }}>Must match the model loaded in LM Studio.</small>
                        </div>

                        <div className="form-group">
                            <label>Temperature: {settings.temperature}</label>
                            <input
                                type="range"
                                name="temperature"
                                min="0"
                                max="1"
                                step="0.05"
                                className="form-control"
                                style={{ padding: '0' }}
                                value={settings.temperature}
                                onChange={handleChange}
                            />
                            <small style={{ color: 'var(--color-text-muted)' }}>Lower = more deterministic, predictable probes.</small>
                        </div>

                        <div className="form-group">
                            <label>Max Tokens</label>
                            <input
                                type="number"
                                name="maxTokens"
                                className="form-control"
                                value={settings.maxTokens}
                                onChange={handleChange}
                            />
                        </div>
                    </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '2rem' }}>
                    <button type="submit" className="btn-primary" style={{ padding: '0.75rem 2rem', fontSize: '1rem' }}>
                        Save Configuration
                    </button>
                </div>
            </form>
        </div>
    );
}
