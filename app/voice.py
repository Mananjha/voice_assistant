import asyncio
import io
import os
import queue
import threading
import uuid
import wave
from fractions import Fraction
from typing import Optional

import numpy as np
import pyttsx3
from faster_whisper import WhisperModel

from av import AudioFrame
from av.audio.resampler import AudioResampler
from aiortc import MediaStreamTrack

from app.memory import clear_memory
from app.graph import ask_agent

# CONFIGURATION
SAMPLE_RATE = 48000
CHANNELS = 1

WHISPER_SAMPLE_RATE = 16000
WHISPER_MODEL = "base.en"

SILENCE_THRESHOLD = 120
SILENCE_DURATION = 0.9

MIN_SPEECH_DURATION = 0.3

# Prevent one speech segment from becoming extremely long
MAX_SPEECH_DURATION = 8.0

GREETING_MIN_FRAMES = 100

TTS_LEAD_SILENCE = 0.3

# Pre-roll frames kept before speech is detected 
PRE_ROLL_FRAMES = 15

TTS_TIMEOUT = 45

print()
print("========================================")
print("Loading Faster-Whisper / Whisper model...")
print(f"Model: {WHISPER_MODEL}")
print("========================================")

try:
    whisper_model = WhisperModel(WHISPER_MODEL)

    print("Whisper model loaded successfully.")

except Exception as e:
    print("ERROR loading Whisper model:")
    print(repr(e))
    raise


class TTSWorker:

    def __init__(self):

        self.jobs = queue.Queue()

        self.thread = threading.Thread(
            target=self._run,
            daemon=True
        )
        self.thread.start()
        print("TTS worker thread started.")

    def _run(self):
        try:
            import pythoncom
            pythoncom.CoInitialize()
            print("COM initialised for TTS thread.")
        except Exception as e:
            print("COM init skipped:", repr(e))
        while True:
            text, out_path, reply = self.jobs.get()
            engine = None
            try:
                engine = pyttsx3.init()

                engine.setProperty("rate", 170)
                engine.setProperty("volume", 1.0)

                engine.save_to_file(text, out_path)
                engine.runAndWait()

                engine.stop()
                engine = None

                if not os.path.exists(out_path):
                    raise RuntimeError(
                        "TTS output file was not created."
                    )

                with open(out_path, "rb") as file:
                    audio_data = file.read()

                if len(audio_data) == 0:
                    raise RuntimeError(
                        "TTS output file is empty."
                    )

                reply.put(("ok", audio_data))

            except Exception as e:

                print("TTS worker error:")
                print(repr(e))

                reply.put(("err", e))

            finally:

                if engine is not None:
                    try:
                        engine.stop()
                    except Exception:
                        pass

                try:
                    if os.path.exists(out_path):
                        os.remove(out_path)
                except Exception:
                    pass


tts_worker = TTSWorker()


def generate_tts(text: str) -> bytes:
    """
    Convert text into WAV audio using pyttsx3,
    executed on the dedicated TTS thread.
    """

    print()
    print("Generating TTS:")
    print(text)

    os.makedirs("data", exist_ok=True)

    out_path = os.path.join(
        "data",
        f"tts_{uuid.uuid4().hex}.wav"
    )

    reply = queue.Queue()

    tts_worker.jobs.put(
        (text, out_path, reply)
    )

    try:
        status, result = reply.get(
            timeout=TTS_TIMEOUT
        )

    except queue.Empty:
        raise RuntimeError(
            "TTS timed out. The speech engine did not respond."
        )

    if status == "err":
        raise result

    return result

def wav_to_mono_48khz(audio_data: bytes) -> np.ndarray:
    """
    Convert WAV bytes into mono 48 kHz int16 PCM.
    """

    try:

        with wave.open(io.BytesIO(audio_data), "rb") as wav:

            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            source_rate = wav.getframerate()
            frame_count = wav.getnframes()

            raw_audio = wav.readframes(frame_count)

        if frame_count == 0:
            return np.array([], dtype=np.int16)


        if sample_width == 2:
            audio = np.frombuffer(
                raw_audio,
                dtype=np.int16
            )

        elif sample_width == 1:
            audio = np.frombuffer(
                raw_audio,
                dtype=np.uint8
            ).astype(np.int16)

            audio = (audio - 128) * 256

        elif sample_width == 4:
            audio = np.frombuffer(
                raw_audio,
                dtype=np.int32
            )

            audio = audio / 65536.0
            audio = audio.astype(np.int16)

        else:
            raise ValueError(
                f"Unsupported WAV sample width: {sample_width}"
            )

        if channels > 1:

            audio = audio.reshape(-1, channels)

            audio = np.mean(
                audio.astype(np.float32),
                axis=1
            )

            audio = np.clip(
                audio,
                -32768,
                32767
            ).astype(np.int16)

        else:
            audio = audio.astype(np.int16)

        if source_rate != SAMPLE_RATE:

            old_length = len(audio)

            if old_length == 0:
                return np.array([], dtype=np.int16)

            new_length = int(
                old_length
                * SAMPLE_RATE
                / source_rate
            )

            if new_length <= 0:
                return np.array([], dtype=np.int16)

            old_indices = np.linspace(
                0,
                old_length - 1,
                old_length
            )

            new_indices = np.linspace(
                0,
                old_length - 1,
                new_length
            )

            audio = np.interp(
                new_indices,
                old_indices,
                audio.astype(np.float32)
            ).astype(np.int16)

        return audio

    except Exception as e:

        print("WAV conversion error:")
        print(repr(e))

        return np.array([], dtype=np.int16)


def frame_to_numpy(
    frame: AudioFrame,
    resampler: AudioResampler
) -> np.ndarray:
    """
    Convert an incoming WebRTC AudioFrame into
    mono int16 PCM samples at SAMPLE_RATE.
    """

    try:

        resampled = resampler.resample(frame)

        if resampled is None:
            return np.array([], dtype=np.int16)

        if not isinstance(resampled, list):
            resampled = [resampled]

        chunks = []

        for item in resampled:

            if item is None:
                continue

            audio = np.asarray(item.to_ndarray())

            chunks.append(
                audio.reshape(-1).astype(np.int16)
            )

        if not chunks:
            return np.array([], dtype=np.int16)

        return np.concatenate(chunks)

    except Exception as e:

        print("Audio frame conversion error:")
        print(repr(e))

        return np.array([], dtype=np.int16)


def calculate_rms(audio: np.ndarray) -> float:
    """
    Calculate RMS volume of int16 audio.
    """

    if audio is None or len(audio) == 0:
        return 0.0

    audio_float = audio.astype(np.float32)

    rms = np.sqrt(
        np.mean(
            np.square(audio_float)
        )
    )

    return float(rms)


class TTSAudioTrack(MediaStreamTrack):

    kind = "audio"

    def __init__(self):

        super().__init__()

        self.audio_queue = asyncio.Queue()

        self.samples = np.array(
            [],
            dtype=np.int16
        )

        self.sample_position = 0

        self.frames_sent = 0

        self.closed = False

    async def add_audio(
        self,
        audio_data: bytes
    ):

        if self.closed:
            print("TTS track already closed.")
            return

        audio = wav_to_mono_48khz(
            audio_data
        )

        if len(audio) == 0:

            print("TTS audio is empty.")

            return

        pad = np.zeros(
            int(SAMPLE_RATE * TTS_LEAD_SILENCE),
            dtype=np.int16
        )

        audio = np.concatenate([pad, audio])

        await self.audio_queue.put(audio)


    def has_pending_audio(self) -> bool:

        return (
            len(self.samples) > 0
            or not self.audio_queue.empty()
        )

    def _build_frame(
        self,
        chunk: np.ndarray
    ) -> AudioFrame:

        frame = AudioFrame(
            format="s16",
            layout="mono",
            samples=len(chunk)
        )

        frame.planes[0].update(
            chunk.tobytes()
        )

        frame.sample_rate = SAMPLE_RATE

        frame.time_base = Fraction(
            1,
            SAMPLE_RATE
        )

        frame.pts = self.sample_position

        self.sample_position += len(chunk)

        self.frames_sent += 1

        return frame

    async def recv(self):

        FRAME_SIZE = 960

        if self.closed:

            silence = np.zeros(
                FRAME_SIZE,
                dtype=np.int16
            )

            return self._build_frame(silence)

        if len(self.samples) < FRAME_SIZE:

            try:

                new_audio = await asyncio.wait_for(
                    self.audio_queue.get(),
                    timeout=0.02
                )

                if new_audio is not None:

                    self.samples = np.concatenate(
                        [
                            self.samples,
                            new_audio
                        ]
                    )

            except asyncio.TimeoutError:

                pass

        if len(self.samples) == 0:

            chunk = np.zeros(
                FRAME_SIZE,
                dtype=np.int16
            )

        else:

            if len(self.samples) >= FRAME_SIZE:

                chunk = self.samples[
                    :FRAME_SIZE
                ]

                self.samples = self.samples[
                    FRAME_SIZE:
                ]

            else:

                chunk = np.zeros(
                    FRAME_SIZE,
                    dtype=np.int16
                )

                chunk[:len(self.samples)] = (
                    self.samples
                )

                self.samples = np.array(
                    [],
                    dtype=np.int16
                )


        await asyncio.sleep(0.02)

        return self._build_frame(chunk)

    async def close_track(self):

        self.closed = True

        self.samples = np.array(
            [],
            dtype=np.int16
        )

        while not self.audio_queue.empty():

            try:
                self.audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break


class VoiceSession:

    def __init__(self, session_id: str):

        self.session_id = session_id

        # Outgoing AI audio
        self.output_track = TTSAudioTrack()

        self.resampler = AudioResampler(
            format="s16",
            layout="mono",
            rate=SAMPLE_RATE
        )

        self.audio_buffer = []

        self.pre_roll = []

        self.speech_started = False
        self.silence_frames = 0

        self.processing = False

        self.running = True
        self.speaking = False
        self.greeting_sent = False

        self.tts_lock = asyncio.Lock()

        self.processing_task: Optional[
            asyncio.Task
        ] = None

        print()
        print("Voice session created:")
        print(self.session_id)

    async def send_greeting(self):

        if not self.running:

            print(
                "Session closed. Greeting cancelled."
            )

            return

        if self.greeting_sent:

            print(
                "Greeting already sent. Skipping."
            )

            return

        self.greeting_sent = True

        for _ in range(300):

            if not self.running:
                return

            if self.output_track.frames_sent > GREETING_MIN_FRAMES:
                break

            await asyncio.sleep(0.02)

        if not self.running:

            return

        print()
        print(
            f"Starting greeting after "
            f"{self.output_track.frames_sent} frames."
        )

        greeting = (
            "Hi, I am the Naikroop AI assistant. "
            "How can I help you today?"
        )

        await self.speak(
            greeting
        )

    async def speak(
        self,
        text: str
    ):
        if not self.running:
            print("Session closed. TTS cancelled.")
            return

        if not text:
            return

        async with self.tts_lock:

            if not self.running:

                return

            self.speaking = True

            try:

                loop = asyncio.get_running_loop()

                audio_data = await loop.run_in_executor(
                    None,
                    generate_tts,
                    text
                )

                if not self.running:

                    return

                duration = 0.0

                try:

                    with wave.open(
                        io.BytesIO(audio_data),
                        "rb"
                    ) as wav:

                        frames = wav.getnframes()
                        rate = wav.getframerate()

                        if rate > 0:

                            duration = (
                                frames / rate
                            )

                except Exception as e:

                    print(
                        "Could not calculate TTS duration:"
                    )

                    print(
                        repr(e)
                    )

                print(
                    f"TTS duration: "
                    f"{duration:.2f}s"
                )

                await self.output_track.add_audio(
                    audio_data
                )

                if not self.running:

                    return

                await asyncio.sleep(
                    duration
                    + TTS_LEAD_SILENCE
                    + 0.8
                )

                print(
                    "AI finished speaking."
                )

            except asyncio.CancelledError:

                print(
                    "TTS task cancelled."
                )

                raise

            except Exception as e:

                print()
                print(
                    "TTS ERROR:"
                )

                print(
                    repr(e)
                )

            finally:

                self.speaking = False

                self.audio_buffer = []
                self.pre_roll = []

                self.speech_started = False
                self.silence_frames = 0

    async def process_audio(
        self,
        frame: AudioFrame
    ):

        if not self.running:
            return

        if self.speaking:
            return

        if self.processing:
            return

        audio = frame_to_numpy(
            frame,
            self.resampler
        )

        if len(audio) == 0:
            return

        rms = calculate_rms(
            audio
        )

        is_speech = (
            rms > SILENCE_THRESHOLD
        )

        if is_speech:

            if not self.speech_started:

                print()
                print(
                    f"Speech started. (RMS: {rms:.1f})"
                )

                self.speech_started = True

                self.audio_buffer = list(self.pre_roll)

                self.pre_roll = []

            self.silence_frames = 0

            self.audio_buffer.append(
                audio
            )

            total_samples = sum(
                len(x)
                for x in self.audio_buffer
            )

            speech_duration = (
                total_samples
                / SAMPLE_RATE
            )

            if speech_duration >= MAX_SPEECH_DURATION:

                print(
                    f"Maximum speech duration "
                    f"reached: "
                    f"{speech_duration:.2f}s"
                )

                self.trigger_finish_speech()

            return

        if not self.speech_started:

            self.pre_roll.append(audio)

            if len(self.pre_roll) > PRE_ROLL_FRAMES:
                self.pre_roll.pop(0)

            return

        self.audio_buffer.append(audio)

        self.silence_frames += len(
            audio
        )

        silence_seconds = (
            self.silence_frames
            / SAMPLE_RATE
        )

        if silence_seconds >= SILENCE_DURATION:

            print(
                f"Silence detected: "
                f"{silence_seconds:.2f}s"
            )

            self.trigger_finish_speech()


    def trigger_finish_speech(self):

        if not self.running:
            return

        if self.processing:
            return


        self.processing = True

        self.processing_task = asyncio.create_task(
            self.finish_speech()
        )

    async def finish_speech(self):

        try:

            if not self.running:
                return

            if not self.audio_buffer:

                self.speech_started = False
                self.silence_frames = 0

                return

            audio = np.concatenate(
                self.audio_buffer
            )

            # Clear immediately.
            self.audio_buffer = []
            self.pre_roll = []

            self.speech_started = False
            self.silence_frames = 0

            duration = (
                len(audio)
                / SAMPLE_RATE
            )

            print()
            print(
                f"Speech duration: "
                f"{duration:.2f}s"
            )

            if duration < MIN_SPEECH_DURATION:

                print(
                    "Speech too short. Ignoring."
                )

                return

            rms = calculate_rms(
                audio
            )

            peak = int(
                np.max(
                    np.abs(audio)
                )
            )

            print(
                f"Speech RMS: {rms:.2f}"
            )

            print(
                f"Speech peak: {peak}"
            )

            text = await self.transcribe(
                audio
            )

            if not self.running:

                print(
                    "Session closed after transcription."
                )

                return

            text = text.strip()

            if not text:

                print(
                    "No speech recognized."
                )

                return

            print()
            print(
                "USER:"
            )

            print(
                text
            )

            loop = asyncio.get_running_loop()

            answer = await loop.run_in_executor(
                None,
                ask_agent,
                self.session_id,
                text
            )

            if not self.running:

                print(
                    "Session closed before AI response."
                )

                return

            if not answer:

                answer = (
                    "I'm sorry, I couldn't "
                    "find an answer to that."
                )

            print()
            print(
                "AI:"
            )

            print(
                answer
            )

            await self.speak(
                answer
            )

        except asyncio.CancelledError:

            print(
                "Speech processing cancelled."
            )

            raise

        except Exception as e:

            print()
            print(
                "SPEECH PROCESSING ERROR:"
            )

            print(
                repr(e)
            )

        finally:

            self.processing = False

    async def transcribe(
        self,
        audio: np.ndarray
    ) -> str:

        if not self.running:

            return ""

        audio_float = (
            audio.astype(
                np.float32
            )
            / 32768.0
        )

        if len(audio_float) == 0:

            return ""

        audio_float = (
            audio_float
            - np.mean(audio_float)
        )

        peak = float(
            np.max(
                np.abs(audio_float)
            )
        )

        rms = float(
            np.sqrt(
                np.mean(
                    audio_float ** 2
                )
            )
        )

        print(
            "Whisper input - "
            f"duration: "
            f"{len(audio_float) / SAMPLE_RATE:.2f}s, "
            f"RMS: {rms:.5f}, "
            f"peak: {peak:.5f}"
        )

        if peak <= 0:

            return ""

        if peak < 0.03:

            gain = min(
                4.0,
                0.03 / peak
            )

            audio_float = (
                audio_float * gain
            )

        audio_float = np.clip(
            audio_float,
            -1.0,
            1.0
        )

        new_length = int(
            len(audio_float)
            * WHISPER_SAMPLE_RATE
            / SAMPLE_RATE
        )

        if new_length <= 0:

            return ""

        old_indices = np.linspace(
            0,
            len(audio_float) - 1,
            len(audio_float)
        )

        new_indices = np.linspace(
            0,
            len(audio_float) - 1,
            new_length
        )

        audio_16k = np.interp(
            new_indices,
            old_indices,
            audio_float
        ).astype(
            np.float32
        )

        loop = asyncio.get_running_loop()

        def run_whisper():

            try:

                segments, info = (
                    whisper_model.transcribe(
                        audio_16k,
                        language="en",
                        beam_size=5,
                        vad_filter=False,
                        condition_on_previous_text=False,
                    )
                )

                text = " ".join(
                    segment.text.strip()
                    for segment in segments
                ).strip()

                print()
                print(
                    "Whisper result:"
                )

                print(
                    repr(text)
                )

                return text

            except Exception as e:

                print()
                print(
                    "WHISPER ERROR:"
                )

                print(
                    repr(e)
                )

                return ""

        return await loop.run_in_executor(
            None,
            run_whisper
        )

    async def close(self):

        if not self.running:

            return

        print()
        print(
            "Closing voice session..."
        )

        self.running = False

        self.speaking = False

        if self.processing_task is not None:

            if not self.processing_task.done():

                self.processing_task.cancel()

        self.audio_buffer = []
        self.pre_roll = []

        self.speech_started = False
        self.silence_frames = 0

        try:

            clear_memory(
                self.session_id
            )

        except Exception as e:

            print(
                "Memory cleanup error:"
            )

            print(
                repr(e)
            )

        try:

            await self.output_track.close_track()

        except Exception as e:

            print(
                "TTS track close error:"
            )

            print(
                repr(e)
            )

        print(
            "Voice session closed."
        )