/**
 * Type definitions for the English Tutor AI voice application.
 * Enforces strict typing with zero `any` usage.
 */

export type ConnectionStatus =
  | 'idle'
  | 'initializing'
  | 'connecting'
  | 'connected'
  | 'disconnecting'
  | 'disconnected'
  | 'error';

export type VoiceState = 'idle' | 'listening' | 'thinking' | 'speaking';

export interface AudioLevels {
  local: number;
  remote: number;
}

export interface SessionStats {
  durationSeconds: number;
  turnCount: number;
}

export interface TutorHookState {
  status: ConnectionStatus;
  voiceState: VoiceState;
  isMuted: boolean;
  errorMessage: string | null;
  audioLevels: AudioLevels;
  studentId: string;
}

export interface TutorHookActions {
  setStudentId: (id: string) => void;
  connect: (idOverride?: string) => Promise<void>;
  disconnect: () => Promise<void>;
  toggleMute: () => void;
  clearError: () => void;
}
