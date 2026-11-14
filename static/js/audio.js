// Web Audio synthesizer. No external assets. Behaves like the prototype's
// TerminalAudio, plus a "stale" tone used when a feed errors.
class TerminalAudio {
    constructor() {
        this.ctx = null;
        this.enabled = true;
    }

    init() {
        if (!this.ctx) {
            const AC = window.AudioContext || window.webkitAudioContext;
            this.ctx = new AC();
        }
    }

    _tone(type, freqStart, freqEnd, gainPeak, duration) {
        if (!this.enabled) return;
        this.init();
        if (this.ctx.state === 'suspended') this.ctx.resume();

        const t0 = this.ctx.currentTime;
        const osc = this.ctx.createOscillator();
        const gain = this.ctx.createGain();
        osc.type = type;
        osc.frequency.setValueAtTime(freqStart, t0);
        osc.frequency.exponentialRampToValueAtTime(freqEnd, t0 + duration);
        gain.gain.setValueAtTime(gainPeak, t0);
        gain.gain.exponentialRampToValueAtTime(0.001, t0 + duration);

        osc.connect(gain);
        gain.connect(this.ctx.destination);
        osc.start(t0);
        osc.stop(t0 + duration);
    }

    playClick() {
        this._tone('sine', 700, 350, 0.04, 0.03);
    }

    playAlert() {
        // Two-note urgency; used for X-class flare or M6+ quake
        this._tone('square', 880, 880, 0.05, 0.08);
        setTimeout(() => this._tone('square', 1100, 1100, 0.05, 0.10), 90);
    }

    playStale() {
        // Feeds that just went stale get a low thunk once, not on every poll
        this._tone('sine', 220, 160, 0.04, 0.15);
    }
}

window.audio = new TerminalAudio();