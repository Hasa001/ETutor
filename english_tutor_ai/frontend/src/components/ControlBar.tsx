import React, { useEffect, useState } from 'react';
import { Mic, MicOff, PhoneOff } from 'lucide-react';
import type { VoiceState } from '../types/tutor';

interface ControlBarProps {
  isMuted: boolean;
  voiceState: VoiceState;
  onToggleMute: () => void;
  onDisconnect: () => void;
}

export const ControlBar: React.FC<ControlBarProps> = React.memo(
  ({ isMuted, voiceState, onToggleMute, onDisconnect }) => {
    const [secondsElapsed, setSecondsElapsed] = useState<number>(0);

    // Track active call duration
    useEffect(() => {
      const timer = setInterval(() => {
        setSecondsElapsed((prev) => prev + 1);
      }, 1000);

      return () => clearInterval(timer);
    }, []);

    const formatDuration = (totalSecs: number) => {
      const mins = Math.floor(totalSecs / 60)
        .toString()
        .padStart(2, '0');
      const secs = (totalSecs % 60).toString().padStart(2, '0');
      return `${mins}:${secs}`;
    };

    return (
      <footer className="control-bar-wrapper" role="region" aria-label="Session Controls">
        {/* Microphone Toggle Button */}
        <button
          type="button"
          className={`control-btn ${isMuted ? 'muted' : 'active'}`}
          onClick={onToggleMute}
          aria-label={isMuted ? 'Unmute microphone' : 'Mute microphone'}
          aria-pressed={!isMuted}
          title={isMuted ? 'Unmute microphone (Space/M)' : 'Mute microphone (Space/M)'}
        >
          {isMuted ? <MicOff size={22} aria-hidden="true" /> : <Mic size={22} aria-hidden="true" />}
          <span className="btn-tooltip">{isMuted ? 'Unmute' : 'Mute'}</span>
        </button>

        {/* Dynamic Center Info: Session Duration & Live State */}
        <div className="session-info" aria-live="off">
          <span className="session-timer" aria-label={`Call duration ${formatDuration(secondsElapsed)}`}>
            {formatDuration(secondsElapsed)}
          </span>
          <div className="audio-wave-indicator" aria-hidden="true">
            <span className={`bar ${voiceState === 'listening' ? 'pulse' : ''}`} />
            <span className={`bar ${voiceState === 'speaking' || voiceState === 'listening' ? 'pulse delay-1' : ''}`} />
            <span className={`bar ${voiceState === 'speaking' ? 'pulse delay-2' : ''}`} />
            <span className={`bar ${voiceState === 'listening' ? 'pulse delay-3' : ''}`} />
          </div>
        </div>

        {/* Disconnect / End Call Button */}
        <button
          type="button"
          className="control-btn end-call"
          onClick={onDisconnect}
          aria-label="End conversation session"
          title="End conversation"
        >
          <PhoneOff size={22} aria-hidden="true" />
          <span className="btn-tooltip">End</span>
        </button>
      </footer>
    );
  }
);

ControlBar.displayName = 'ControlBar';
