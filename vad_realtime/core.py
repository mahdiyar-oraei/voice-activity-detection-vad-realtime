"""Frame-level VAD core: webrtcvad classification plus speech segmentation.

Pure-python state machines with no I/O so the same logic backs both the
websocket demo server and in-process consumers (e.g. a LiveKit VAD adapter).
Audio frames are s16le mono; the default geometry is 20 ms at 16 kHz.
"""
from __future__ import annotations

import webrtcvad

DEFAULT_SAMPLE_RATE = 16000
DEFAULT_FRAME_SAMPLES = 320  # 20 ms @ 16 kHz
BYTES_PER_SAMPLE = 2


class FrameVAD:
    """Classifies one fixed-size audio frame at a time."""

    def __init__(self, aggressiveness: int = 3, sample_rate: int = DEFAULT_SAMPLE_RATE,
                 frame_samples: int = DEFAULT_FRAME_SAMPLES) -> None:
        self._vad = webrtcvad.Vad(aggressiveness)
        self.sample_rate = sample_rate
        self.frame_samples = frame_samples
        self.frame_bytes = frame_samples * BYTES_PER_SAMPLE
        self.frame_duration = frame_samples / sample_rate

    def is_speech(self, frame: bytes) -> bool:
        """True if the frame contains speech. Short frames are padded with silence
        (browser clients don't always deliver exact buffer sizes)."""
        if len(frame) < self.frame_bytes:
            frame = frame.ljust(self.frame_bytes, b"\x00")
        return self._vad.is_speech(frame[:self.frame_bytes], sample_rate=self.sample_rate)


class Segmenter:
    """Turns a per-frame speech/silence stream into speech segments.

    push() returns "start" on the frame where accumulated speech reaches
    min_speech_duration, "end" on the frame where accumulated silence reaches
    min_silence_duration while speaking, else None. The debounce mirrors the
    tuning the voice agent uses for Silero (D-024): a lone click or pop never
    starts a segment, and a mid-sentence breath never ends one.
    """

    def __init__(self, *, min_speech_duration: float = 0.1, min_silence_duration: float = 0.55,
                 frame_duration: float = DEFAULT_FRAME_SAMPLES / DEFAULT_SAMPLE_RATE) -> None:
        self.frame_duration = frame_duration
        self._min_speech_frames = max(1, round(min_speech_duration / frame_duration))
        self._min_silence_frames = max(1, round(min_silence_duration / frame_duration))
        self.reset()

    def reset(self) -> None:
        """Hard segment boundary: the next frame starts fresh."""
        self.speaking = False
        self._speech_run = 0
        self._silence_run = 0

    @property
    def accumulated_speech(self) -> float:
        return self._speech_run * self.frame_duration

    @property
    def accumulated_silence(self) -> float:
        return self._silence_run * self.frame_duration

    def push(self, is_speech: bool) -> str | None:
        if is_speech:
            self._speech_run += 1
            self._silence_run = 0
            if not self.speaking and self._speech_run >= self._min_speech_frames:
                self.speaking = True
                return "start"
            return None
        self._silence_run += 1
        self._speech_run = 0
        if self.speaking and self._silence_run >= self._min_silence_frames:
            self.speaking = False
            return "end"
        return None
