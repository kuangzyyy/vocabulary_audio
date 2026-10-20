/**
 * Temporary local "audio" for Phase 1.
 *
 * No real pronunciation is fetched yet. A short Web Audio tone makes the click
 * audible, while the UI shows an explicit "模拟播放" message. If Web Audio is
 * unavailable, the visual feedback still works.
 */

let audioContext = null;

export function playSimulatedTone(kind = 'word') {
  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) {
      return;
    }
    audioContext ??= new AudioContextClass();
    if (audioContext.state === 'suspended') {
      void audioContext.resume();
    }

    const now = audioContext.currentTime;
    const oscillator = audioContext.createOscillator();
    const gain = audioContext.createGain();

    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(kind === 'sentence' ? 520 : 660, now);
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.06, now + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.16);

    oscillator.connect(gain);
    gain.connect(audioContext.destination);
    oscillator.start(now);
    oscillator.stop(now + 0.18);
  } catch (error) {
    console.warn('Simulated audio is unavailable:', error);
  }
}
