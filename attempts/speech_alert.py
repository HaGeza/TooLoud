import sys
import os
import argparse
import sounddevice as sd
import numpy as np
import simpleaudio as sa
import webrtcvad

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Monitor sound levels for human speech and trigger an alarm if detected.")
parser.add_argument("-t", "--threshold_high", type=float, default=0.1, help="High noise threshold level for an immediate alarm (0.0 to 1.0). Default is 0.5.")
parser.add_argument("-l", "--threshold_low", type=float, default=0.02, help="Lower noise threshold level for extended-duration alarms (0.0 to 1.0). Default is 0.3.")
parser.add_argument("-f", "--alarm_file", type=str, default="ship.wav", help="Path to the alarm sound file (must be a .wav file). Default is 'alarm.wav'.")
parser.add_argument("-d", "--alarm_duration", type=float, default=2.0, help="Minimum time in seconds between alarm repeats. Default is 2 seconds.")
parser.add_argument("-v", "--vad_mode", type=int, default=1, choices=[0, 1, 2, 3], help="WebRTC VAD aggressiveness mode (0=least, 3=most). Default is 1.")
args = parser.parse_args()

# Assign settings from arguments
THRESHOLD_HIGH = args.threshold_high
THRESHOLD_LOW = args.threshold_low
ALARM_FILE = os.path.join("sounds", args.alarm_file)
ALARM_DURATION = args.alarm_duration
VAD_MODE = args.vad_mode

# Load the alarm sound
try:
    alarm_wave = sa.WaveObject.from_wave_file(ALARM_FILE)
except FileNotFoundError:
    print(f"Error: Alarm file '{ALARM_FILE}' not found.")
    exit(1)

# Initialize WebRTC VAD
vad = webrtcvad.Vad()
vad.set_mode(VAD_MODE)  # Adjust aggressiveness (0=least aggressive, 3=most aggressive)

# Speech detection parameters
FRAME_DURATION = 30  # in ms (valid values: 10, 20, 30)
SAMPLE_RATE = 16000  # WebRTC VAD works best with 16 kHz
FRAME_SIZE = int(SAMPLE_RATE * FRAME_DURATION / 1000)  # Samples per frame

def is_speech(audio_data):
    """Detect if the audio frame contains speech using WebRTC VAD."""
    return vad.is_speech(audio_data, SAMPLE_RATE)

# Variable to track extended duration condition
extended_counter = 0
# Initialize alarm state
alarm_active = False

def trigger_alarm():
    """Play the alarm sound and enforce a cooldown period."""
    global alarm_active
    alarm_active = True
    alarm = alarm_wave.play()
    alarm.wait_done()
    sd.sleep(int(ALARM_DURATION * 1000))
    alarm_active = False

def check_sound_level(indata, frames, time, status):
    """Callback function to process audio input."""
    global extended_counter, alarm_active

    if status:
        print(f"Error: {status}")

    # Convert input to 16-bit PCM format for VAD
    audio_data = (indata[:, 0] * 32767).astype(np.int16).tobytes()

    # Check if the audio contains speech
    if is_speech(audio_data):
        # Compute RMS (root mean square) level of the sound input
        rms_level = np.sqrt(np.mean(indata**2))
        percentage_high = min(100, int((rms_level / THRESHOLD_HIGH) * 100))
        percentage_low = min(100, int((rms_level / THRESHOLD_LOW) * 100))

        # Print noise levels and status
        sys.stdout.write(f"\rCurrent Noise Level: {rms_level:.3f} | High: {percentage_high}% | Low: {percentage_low}%   ")
        sys.stdout.flush()
        if rms_level > THRESHOLD_HIGH:
            if not alarm_active:
                sys.stdout.write("\rImmediate noise detected! Triggering alarm...                          ")
                sys.stdout.flush()
                trigger_alarm()
                return
        # Check if noise exceeds the low threshold for an extended duration
        elif rms_level > THRESHOLD_LOW:
            extended_counter += 5
            if extended_counter > 50:
                sys.stdout.write("\rExtended noise detected! Triggering alarm...")
                sys.stdout.flush()
                trigger_alarm()
                return
    else:
        sys.stdout.write("\rNo speech detected.                           ")
        sys.stdout.flush()

    # Decrement counter if no speech above low threshold is detected
    extended_counter = max(0, extended_counter - 1)


# Main script with proper cleanup
try:
    print(f"Monitoring for human speech... (Thresholds: {THRESHOLD_HIGH}, {THRESHOLD_LOW}, Alarm File: {ALARM_FILE}, VAD Mode: {VAD_MODE})")
    print("Press Ctrl+C to stop.")
    with sd.InputStream(callback=check_sound_level, channels=1, samplerate=SAMPLE_RATE, blocksize=FRAME_SIZE):
        while True:
            sd.sleep(100)  # Keep the stream alive, check every 100ms
except KeyboardInterrupt:
    print("\nExiting...")
finally:
    print("Stopping audio stream. Goodbye!")
