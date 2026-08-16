import React from 'react';
import { VoiceOrb } from './VoiceOrb';
import { StatusBadge } from './StatusBadge';
import { ControlBar } from './ControlBar';
import { User } from 'lucide-react';
import type { ConnectionStatus, VoiceState, AudioLevels } from '../types/tutor';

interface ConversationViewProps {
  studentId: string;
  status: ConnectionStatus;
  voiceState: VoiceState;
  audioLevels: AudioLevels;
  isMuted: boolean;
  onToggleMute: () => void;
  onDisconnect: () => void;
}

export const ConversationView: React.FC<ConversationViewProps> = ({
  studentId,
  status,
  voiceState,
  audioLevels,
  isMuted,
  onToggleMute,
  onDisconnect,
}) => {
  const getFeedbackHeadline = () => {
    switch (voiceState) {
      case 'speaking':
        return 'Tutor is speaking...';
      case 'listening':
        return isMuted ? 'Microphone is muted' : 'Listening to you...';
      case 'thinking':
        return 'Analyzing and formulating response...';
      case 'idle':
      default:
        return `Ready for conversation`;
    }
  };

  const getFeedbackSubtext = () => {
    if (isMuted) return 'Press unmute to speak with your tutor.';
    switch (voiceState) {
      case 'speaking':
        return 'Feel free to speak whenever you want to interrupt.';
      case 'listening':
        return 'Speak naturally in English about any topic.';
      case 'thinking':
        return 'Checking grammar and preparing feedback.';
      default:
        return 'Say hello or ask a question to begin.';
    }
  };

  return (
    <main className="conversation-container" role="main">
      {/* Top Header with Student Identifier Chip & Status Beacon */}
      <header className="conversation-header">
        <div className="user-badge" aria-label={`Logged in as ${studentId}`}>
          <User size={15} className="user-icon" aria-hidden="true" />
          <span className="user-id-text">{studentId}</span>
        </div>
        <StatusBadge status={status} voiceState={voiceState} />
      </header>

      {/* Main Center Stage: Animated Voice Visualizer */}
      <section className="visualizer-stage" aria-label="Voice Visualizer">
        <VoiceOrb
          state={voiceState}
          audioLevel={voiceState === 'speaking' ? audioLevels.remote : audioLevels.local}
          size="large"
        />

        {/* Dynamic Typography & Interactive Cue */}
        <div className="speech-feedback" aria-live="polite">
          <h2 className="feedback-title">{getFeedbackHeadline()}</h2>
          <p className="feedback-desc">{getFeedbackSubtext()}</p>
        </div>
      </section>

      {/* Bottom Accessible Controls */}
      <ControlBar
        isMuted={isMuted}
        voiceState={voiceState}
        onToggleMute={onToggleMute}
        onDisconnect={onDisconnect}
      />
    </main>
  );
};
