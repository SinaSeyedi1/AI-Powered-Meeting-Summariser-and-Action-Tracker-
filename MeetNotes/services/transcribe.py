from __future__ import annotations
import io, tempfile
from typing import Tuple
from pydub import AudioSegment

def _extract_wav(file_bytes: bytes) -> Tuple[str, int]:
    # Extract audio as 16k mono wav to a temp file. Returns path and duration seconds.
    audio = AudioSegment.from_file(io.BytesIO(file_bytes))
    duration_sec = int(len(audio) / 1000)
    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    audio.export(tf.name, format="wav")
    return tf.name, duration_sec

def transcribe_local_faster_whisper(file_bytes: bytes, model_size: str = "base") -> Tuple[str, int]:
    # Transcribe using faster-whisper locally. Requires 'faster-whisper' and ffmpeg installed.
    from faster_whisper import WhisperModel
    wav_path, duration = _extract_wav(file_bytes)
    model = WhisperModel(model_size, compute_type="float32")
    segments, _info = model.transcribe(wav_path, vad_filter=True)
    transcript = ""
    for seg in segments:
        transcript += seg.text.strip() + " "
    return transcript.strip(), duration
