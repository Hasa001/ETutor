import React from 'react';
import type { VoiceState } from '../types/tutor';

interface VoiceOrbProps {
  state: VoiceState;
  audioLevel?: number;
  size?: 'small' | 'medium' | 'large';
}

export const VoiceOrb: React.FC<VoiceOrbProps> = React.memo(({ state, audioLevel = 0, size = 'large' }) => {
  // Scale dynamic glow intensity based on audio activity
  const dynamicScale = state === 'speaking' || state === 'listening' ? 1 + Math.min(audioLevel * 0.4, 0.25) : 1;

  return (
    <div
      className={`voice-orb-wrapper ${size}`}
      role="img"
      aria-label={`AI voice status: ${state}`}
    >
      {/* Outer ambient radiant pulses */}
      <div className={`orb-wave ring-1 ${state}`} />
      <div className={`orb-wave ring-2 ${state}`} />
      <div className={`orb-wave ring-3 ${state}`} />

      {/* Core animated orb sphere */}
      <div
        className={`orb-core ${state}`}
        style={{
          transform: `scale(${dynamicScale})`,
        }}
      >
        <div className="orb-highlight" />
        <div className="orb-inner-shadow" />
      </div>
    </div>
  );
});

VoiceOrb.displayName = 'VoiceOrb';
