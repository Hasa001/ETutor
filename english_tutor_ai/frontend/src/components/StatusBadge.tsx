import React from 'react';
import type { ConnectionStatus, VoiceState } from '../types/tutor';

interface StatusBadgeProps {
  status: ConnectionStatus;
  voiceState: VoiceState;
}

export const StatusBadge: React.FC<StatusBadgeProps> = React.memo(({ status, voiceState }) => {
  const getStatusText = () => {
    if (status === 'initializing' || status === 'connecting') return 'Connecting...';
    if (status === 'disconnecting') return 'Disconnecting...';
    if (status === 'error') return 'Connection Error';
    if (status === 'connected') {
      switch (voiceState) {
        case 'speaking':
          return 'Tutor Speaking';
        case 'listening':
          return 'Listening...';
        case 'thinking':
          return 'Thinking...';
        case 'idle':
        default:
          return 'Connected & Ready';
      }
    }
    return 'Offline';
  };

  const getBadgeClass = () => {
    if (status === 'error') return 'badge-error';
    if (status === 'connecting' || status === 'initializing') return 'badge-warning';
    if (status === 'connected') {
      if (voiceState === 'speaking') return 'badge-speaking';
      if (voiceState === 'listening') return 'badge-listening';
      return 'badge-success';
    }
    return 'badge-offline';
  };

  return (
    <div
      className={`status-badge ${getBadgeClass()}`}
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <span className="beacon-dot" aria-hidden="true" />
      <span className="badge-label">{getStatusText()}</span>
    </div>
  );
});

StatusBadge.displayName = 'StatusBadge';
