"""Stream a 16 kHz mono s16le WAV to the VAD server and report the flags.

Usage: python test_client.py <file.wav> [ws://host:port]
"""
import asyncio
import sys
import wave
from collections import Counter

import websockets

FRAME_BYTES = 640  # 20 ms @ 16 kHz s16le


async def run(path, url):
    with wave.open(path, "rb") as wf:
        assert wf.getframerate() == 16000 and wf.getnchannels() == 1, \
            f"need 16 kHz mono, got {wf.getframerate()} Hz {wf.getnchannels()}ch"
        audio = wf.readframes(wf.getnframes())

    flags = []
    async with websockets.connect(url) as ws:
        for i in range(0, len(audio) - FRAME_BYTES + 1, FRAME_BYTES):
            await ws.send(audio[i:i + FRAME_BYTES])
            flags.append(await ws.recv())

    print("".join(flags))
    counts = Counter(flags)
    total = len(flags)
    print(f"\nframes={total} voice={counts['1']} ({100*counts['1']/total:.0f}%) "
          f"silence={counts['_']} idle-cuts={counts['X']}")


if __name__ == "__main__":
    wav = sys.argv[1]
    url = sys.argv[2] if len(sys.argv) > 2 else "ws://localhost:5000"
    asyncio.run(run(wav, url))
