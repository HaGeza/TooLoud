import sys
import os
import argparse
import time
import sounddevice as sd
import numpy as np
import simpleaudio as sa
import webrtcvad

# Parse command-line arguments
parser = argparse.ArgumentParser(
    description="Monitor sound levels and trigger an alarm if a threshold is exceeded."
)
parser.add_argument(
    "-t",
    "--threshold",
    type=float,
    default=0.2,
    help="Noise threshold level (0.0 to 1.0).",
)
parser.add_argument(
    "-s",
    "--speech_threshold",
    type=float,
    default=0.05,
    help="Speech threshold level (0.0 to 1.0).0.",
)
parser.add_argument(
    "-f",
    "--alarm_file",
    type=str,
    default="ship.wav",
    help="Path to the alarm sound file (must be a .wav file).",
)
parser.add_argument(
    "-d",
    "--alarm_duration",
    type=float,
    default=3.0,
    help="Minimum time in seconds between alarm repeats..",
)
parser.add_argument(
    "-v",
    "--vad_level",
    type=int,
    default=1,
    help="VAD aggressiveness level (0 to 3).",
)
args = parser.parse_args()


class SoundAlerter:
    def __init__(
        self,
        threshold,
        speech_threshold,
        alarm_wave,
        alarm_duration,
        sample_rate=16000,
        vad_level=1,
    ):
        self.threshold = threshold
        self.speech_threshold = speech_threshold
        self.alarm_wave = alarm_wave
        self.alarm_duration = int(alarm_duration * 1000)

        self.alarm_active = False
        self.last_alarm_time = 0

        # Initialize VAD (Voice Activity Detection)
        self.vad = webrtcvad.Vad(vad_level)
        self.sample_rate = sample_rate
        self.frame_duration = 30  # ms
        self.frame_size = int(self.sample_rate * self.frame_duration / 1000)

    def trigger_alarm(self, message):
        """Play the alarm sound."""

        current_time = time.time()
        if (
            not self.alarm_active
            and (current_time - self.last_alarm_time) * 1000 >= self.alarm_duration * 2
        ):
            # Print the message
            sys.stdout.write(message)
            sys.stdout.flush()
            # Play the alarm sound
            alarm = self.alarm_wave.play()
            self.alarm_active = True
            self.last_alarm_time = current_time
            alarm.wait_done()
            # Reset alarm after a delay
            sd.sleep(self.alarm_duration)
            self.alarm_active = False

    def is_speech(self, audio_data):
        """Check if the audio data contains speech."""
        return self.vad.is_speech(audio_data, self.sample_rate)

    def check_sound_level(self, indata, frames, time, status):
        """Callback function to process audio input."""
        if status:
            print(f"Error: {status}")

        # Compute RMS (root mean square) level of the sound input
        normalized_data = indata / 32768.0
        rms_level = np.sqrt(np.mean(normalized_data**2))
        percentage = min(100, int((rms_level / self.threshold) * 100))

        suffix = "(ALARM!)" if percentage >= 100 else " " * 10
        sys.stdout.write(
            f"\rCurrent Noise Level: {rms_level:.3f} | {percentage}% of threshold {suffix}"
        )
        sys.stdout.flush()

        if rms_level > self.threshold:
            self.trigger_alarm("\nNoise level exceeded threshold! (ALARM!)\n")

        # Speech recognition
        audio_data = indata[:, 0].tobytes()
        if rms_level > self.speech_threshold and self.is_speech(audio_data):
            self.trigger_alarm("\nSpeech level exceeded threshold! (ALARM!)\n")


# Load the alarm sound
alarm_path = os.path.join("sounds", args.alarm_file)
try:
    alarm_wave_ = sa.WaveObject.from_wave_file(alarm_path)
except FileNotFoundError:
    print(f"Error: Alarm file '{args.alarm_file}' not found.")
    sys.exit(1)

sample_rate = 16000
alerter = SoundAlerter(
    args.threshold, args.speech_threshold, alarm_wave_, args.alarm_duration, sample_rate
)

try:
    print("Monitoring sound levels... Press Ctrl+C to stop.")
    with sd.InputStream(
        callback=alerter.check_sound_level,
        channels=1,
        samplerate=sample_rate,
        dtype="int16",
        blocksize=alerter.frame_size,
    ):
        while True:
            sd.sleep(100)  # Keep the stream alive, check every 100ms
except KeyboardInterrupt:
    print("\nExiting...")
finally:
    print("Stopping audio stream. Goodbye!")
