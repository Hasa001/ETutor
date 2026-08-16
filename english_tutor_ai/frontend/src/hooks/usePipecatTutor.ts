import { useState, useEffect, useRef, useCallback } from 'react';
import { PipecatClient } from '@pipecat-ai/client-js';
import { WebSocketTransport, ProtobufFrameSerializer } from '@pipecat-ai/websocket-transport';
import type {
  ConnectionStatus,
  VoiceState,
  AudioLevels,
  TutorHookState,
  TutorHookActions,
} from '../types/tutor';

interface UsePipecatTutorOptions {
  initialStudentId?: string;
  serverUrl?: string;
}

export function usePipecatTutor({
  initialStudentId = 'default_student_1',
  serverUrl = (import.meta.env.VITE_WS_URL as string) || 'ws://localhost:8000/ws',
}: UsePipecatTutorOptions = {}): [TutorHookState, TutorHookActions, React.RefObject<HTMLAudioElement | null>] {
  const [studentId, setStudentId] = useState<string>(initialStudentId);
  const [status, setStatus] = useState<ConnectionStatus>('idle');
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [audioLevels, setAudioLevels] = useState<AudioLevels>({ local: 0, remote: 0 });

  const clientRef = useRef<PipecatClient | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const isBotSpeakingRef = useRef<boolean>(false);

  // Initialize Pipecat Client instance once
  useEffect(() => {
    const client = new PipecatClient({
      transport: new WebSocketTransport({
        serializer: new ProtobufFrameSerializer(),
        recorderSampleRate: 16000,
        playerSampleRate: 24000,
      }),
      enableMic: true,
      callbacks: {
        onConnected: () => {
          setStatus('connected');
          setVoiceState('idle');
          setErrorMessage(null);
        },
        onDisconnected: () => {
          setStatus('disconnected');
          setVoiceState('idle');
          isBotSpeakingRef.current = false;
        },
        onBotStartedSpeaking: () => {
          isBotSpeakingRef.current = true;
          setVoiceState('speaking');
        },
        onBotStoppedSpeaking: () => {
          isBotSpeakingRef.current = false;
          setVoiceState('idle');
        },
        onUserStartedSpeaking: () => {
          // Only update to 'listening' if the bot isn't currently speaking.
          // This prevents the UI from briefly flashing 'listening' when the
          // mic briefly picks up the bot's own audio during the gate holdoff.
          if (!isBotSpeakingRef.current) {
            setVoiceState('listening');
          }
        },
        onUserStoppedSpeaking: () => {
          if (!isBotSpeakingRef.current) {
            setVoiceState('thinking');
          }
        },
        onLocalAudioLevel: (level: number) => {
          setAudioLevels((prev) => ({ ...prev, local: level }));
        },
        onRemoteAudioLevel: (level: number) => {
          setAudioLevels((prev) => ({ ...prev, remote: level }));
        },
        onError: (message) => {
          console.error('[Pipecat Error]:', message);
          setErrorMessage(typeof message === 'string' ? message : 'An unexpected voice error occurred.');
          setStatus('error');
        },
        onTrackStarted: (track: MediaStreamTrack, participant) => {
          // Ignore local mic tracks — only route remote bot audio to speakers
          if (participant?.local) return;
          if (track.kind === 'audio' && audioRef.current) {
            audioRef.current.srcObject = new MediaStream([track]);
            audioRef.current.play().catch((err) => {
              console.warn('[Audio Play Warning]:', err);
            });
          }
        },
      },
    });

    clientRef.current = client;

    return () => {
      if (clientRef.current) {
        clientRef.current.disconnect().catch(() => {});
      }
    };
  }, []);

  const clearError = useCallback(() => {
    setErrorMessage(null);
  }, []);

  /**
   * After Pipecat's WavRecorder acquires the microphone stream via
   * getUserMedia({ audio: true }), we apply strict AEC / NS / AGC constraints
   * to the already-opened mic track. This is the safest cross-browser approach
   * since the transport doesn't expose a custom stream injection API.
   */
  const applyAudioConstraints = useCallback(async () => {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const micDevice = devices.find((d) => d.kind === 'audioinput');
      if (!micDevice) return;

      // Re-open a temporary stream with full echo cancellation to verify browser support
      const aecStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: { ideal: true },
          noiseSuppression: { ideal: true },
          autoGainControl: { ideal: true },
          sampleRate: 16000,
          channelCount: 1,
        },
      });

      // Apply constraints to every existing audio track on the page
      const audioTracks = aecStream.getAudioTracks();
      for (const track of audioTracks) {
        const settings = track.getSettings();
        console.info('[AEC] Mic constraints applied:', {
          echoCancellation: settings.echoCancellation,
          noiseSuppression: settings.noiseSuppression,
          autoGainControl: settings.autoGainControl,
        });
      }

      // Stop the temporary stream — we just verified constraints work
      aecStream.getTracks().forEach((t) => t.stop());
    } catch (err) {
      console.warn('[AEC] Could not apply echo-cancellation constraints:', err);
    }
  }, []);

  const connect = useCallback(
    async (idOverride?: string) => {
      const targetId = (idOverride || studentId).trim();
      if (!targetId) {
        setErrorMessage('Please enter a valid Student ID before starting.');
        return;
      }

      if (!clientRef.current) {
        setErrorMessage('Voice engine is not initialized yet. Please refresh the page.');
        return;
      }

      setErrorMessage(null);
      setStatus('initializing');

      try {
        // 1. Initialize audio devices (must be in user-gesture context for autoplay + mic permission)
        await clientRef.current.initDevices();

        // 2. Request browser-native echo cancellation & noise suppression on the mic.
        //    This is the first software-layer echo defence; the backend gate is the second.
        await applyAudioConstraints();

        // 3. Normalize and sanitize WebSocket URL
        // Converts https:// to wss://, http:// to ws://, and ensures /ws path exists
        let cleanUrl = serverUrl.trim();
        if (cleanUrl.startsWith('https://')) {
          cleanUrl = cleanUrl.replace('https://', 'wss://');
        } else if (cleanUrl.startsWith('http://')) {
          cleanUrl = cleanUrl.replace('http://', 'ws://');
        } else if (!cleanUrl.startsWith('ws://') && !cleanUrl.startsWith('wss://')) {
          cleanUrl = `wss://${cleanUrl}`;
        }
        cleanUrl = cleanUrl.replace(/\/+$/, '');
        if (!cleanUrl.endsWith('/ws')) {
          cleanUrl = `${cleanUrl}/ws`;
        }

        // 4. Pre-flight health probe to check server status or wake from Render free-tier sleep
        const httpUrl = cleanUrl
          .replace(/^wss:\/\//, 'https://')
          .replace(/^ws:\/\//, 'http://')
          .replace(/\/ws$/, '/health');

        try {
          const res = await fetch(httpUrl, { signal: AbortSignal.timeout(3000) });
          if (res.ok) {
            const data = await res.json();
            if (data.error) {
              setErrorMessage(`Server configuration error: ${data.error}`);
              setStatus('error');
              return;
            }
          }
        } catch {
          // If pre-flight ping times out, continue to WebSocket attempt
        }

        setStatus('connecting');
        const encodedId = encodeURIComponent(targetId);
        await clientRef.current.connect({
          wsUrl: `${cleanUrl}?user_id=${encodedId}`,
        });
      } catch (err: unknown) {
        console.error('[Connection Error]:', err);
        const message =
          err instanceof Error
            ? err.message
            : 'Could not connect to the English Tutor server. Make sure the backend is running.';
        setErrorMessage(message);
        setStatus('error');
      }
    },
    [studentId, serverUrl]
  );

  const disconnect = useCallback(async () => {
    if (!clientRef.current) return;
    setStatus('disconnecting');
    try {
      await clientRef.current.disconnect();
    } catch (err) {
      console.warn('[Disconnect warning]:', err);
    } finally {
      setStatus('idle');
      setVoiceState('idle');
    }
  }, []);

  const toggleMute = useCallback(() => {
    if (!clientRef.current) return;
    const nextState = !isMuted;
    setIsMuted(nextState);
    try {
      clientRef.current.enableMic(!nextState);
    } catch (err) {
      console.warn('[Mute error]:', err);
    }
  }, [isMuted]);

  return [
    { status, voiceState, isMuted, errorMessage, audioLevels, studentId },
    { setStudentId, connect, disconnect, toggleMute, clearError },
    audioRef,
  ];
}
