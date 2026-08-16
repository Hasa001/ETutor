import React from 'react';
import { usePipecatTutor } from './hooks/usePipecatTutor';
import { SetupScreen } from './components/SetupScreen';
import { ConversationView } from './components/ConversationView';
import './index.css';

export default function App(): React.JSX.Element {
  const [
    { status, voiceState, isMuted, errorMessage, audioLevels, studentId },
    { setStudentId, connect, disconnect, toggleMute, clearError },
    audioRef,
  ] = usePipecatTutor();

  const isSessionActive = status === 'connected';

  return (
    <div className="app-viewport">
      {/* Hidden audio element for browser audio playback */}
      <audio
        ref={audioRef}
        autoPlay
        playsInline
        aria-hidden="true"
      />

      {/* Main Container Card */}
      <div className="app-card" role="application" aria-label="English Tutor Voice Interface">
        {!isSessionActive ? (
          <SetupScreen
            studentId={studentId}
            status={status}
            errorMessage={errorMessage}
            onStudentIdChange={setStudentId}
            onConnect={() => connect()}
            onClearError={clearError}
          />
        ) : (
          <ConversationView
            studentId={studentId}
            status={status}
            voiceState={voiceState}
            audioLevels={audioLevels}
            isMuted={isMuted}
            onToggleMute={toggleMute}
            onDisconnect={disconnect}
          />
        )}
      </div>
    </div>
  );
}
