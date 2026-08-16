import React, { useState } from 'react';
import { VoiceOrb } from './VoiceOrb';
import { Sparkles, ArrowRight, AlertCircle, Loader2 } from 'lucide-react';
import type { ConnectionStatus } from '../types/tutor';

interface SetupScreenProps {
  studentId: string;
  status: ConnectionStatus;
  errorMessage: string | null;
  onStudentIdChange: (id: string) => void;
  onConnect: () => void;
  onClearError: () => void;
}

export const SetupScreen: React.FC<SetupScreenProps> = ({
  studentId,
  status,
  errorMessage,
  onStudentIdChange,
  onConnect,
  onClearError,
}) => {
  const [localError, setLocalError] = useState<string | null>(null);
  const isLoading = status === 'initializing' || status === 'connecting';

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!studentId.trim()) {
      setLocalError('Please enter a Student ID to continue.');
      return;
    }
    setLocalError(null);
    onClearError();
    onConnect();
  };

  const displayedError = errorMessage || localError;

  return (
    <main className="setup-container" role="main">
      <header className="setup-header">
        <div className="preview-orb-container">
          <VoiceOrb state="idle" size="medium" />
        </div>
        <div className="badge-pill">
          <Sparkles size={14} className="sparkle-icon" aria-hidden="true" />
          <span>AI-Powered English Tutor</span>
        </div>
        <h1 className="title-headline">Personalized Language Learning</h1>
        <p className="subtitle-desc">
          Connect with your AI tutor to practice conversational English with real-time feedback and persistent long-term memory.
        </p>
      </header>

      <form className="setup-form" onSubmit={handleSubmit} noValidate>
        <div className="form-field">
          <label htmlFor="student-id-input" className="field-label">
            Student Profile Identifier
          </label>
          <div className="input-wrapper">
            <input
              id="student-id-input"
              type="text"
              className={`text-input ${displayedError ? 'input-error' : ''}`}
              value={studentId}
              onChange={(e) => {
                onStudentIdChange(e.target.value);
                if (displayedError) {
                  setLocalError(null);
                  onClearError();
                }
              }}
              placeholder="e.g., student_101 or your name"
              disabled={isLoading}
              autoComplete="username"
              required
              aria-required="true"
              aria-invalid={!!displayedError}
              aria-describedby={displayedError ? 'setup-error-msg' : undefined}
            />
          </div>
        </div>

        {displayedError && (
          <div id="setup-error-msg" className="error-alert" role="alert" aria-live="assertive">
            <AlertCircle size={18} className="error-icon" aria-hidden="true" />
            <span>{displayedError}</span>
          </div>
        )}

        <button
          type="submit"
          className="submit-btn"
          disabled={isLoading}
          aria-busy={isLoading}
        >
          {isLoading ? (
            <>
              <Loader2 size={20} className="spin-icon" aria-hidden="true" />
              <span>Connecting Tutor...</span>
            </>
          ) : (
            <>
              <span>Begin Session</span>
              <ArrowRight size={18} aria-hidden="true" />
            </>
          )}
        </button>
      </form>

      <footer className="features-list" aria-label="Key Features">
        <div className="feature-item">
          <span className="feature-dot" aria-hidden="true" />
          <span>Groq Whisper STT</span>
        </div>
        <div className="feature-item">
          <span className="feature-dot" aria-hidden="true" />
          <span>Kokoro HD Voice</span>
        </div>
        <div className="feature-item">
          <span className="feature-dot" aria-hidden="true" />
          <span>Mem0 Vector Memory</span>
        </div>
      </footer>
    </main>
  );
};
