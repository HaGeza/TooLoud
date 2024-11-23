import sys
import os
import argparse
import sounddevice as sd
import numpy as np
import simpleaudio as sa

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Monitor sound levels and trigger an alarm if a threshold is exceeded.")
parser.add_argument("--threshold", type=float, default=0.05, help="Noise threshold level (0.0 to 1.0). Default is 0.5.")
parser.add_argument("--alarm_file", type=str, default="ship.wav", help="Path to the alarm sound file (must be a .wav file). Default is 'alarm.wav'.")
parser.add_argument("--alarm_duration", type=float, default=2.0, help="Minimum time in seconds between alarm repeats. Default is 2 seconds.")
args = parser.parse_args()

# Assign settings from arguments
THRESHOLD = args.threshold
ALARM_FILE = os.path.join("sounds", args.alarm_file)
ALARM_DURATION = args.alarm_duration

# Load the alarm sound
try:
    alarm_wave = sa.WaveObject.from_wave_file(ALARM_FILE)
except FileNotFoundError:
    print(f"Error: Alarm file '{ALARM_FILE}' not found.")
    exit(1)

def check_sound_level(indata, frames, time, status):
    """Callback function to process audio input."""
    if status:
        print(f"Error: {status}")

    # Compute RMS (root mean square) level of the sound input
    rms_level = np.sqrt(np.mean(indata**2))
    percentage = min(100, int((rms_level / THRESHOLD) * 100))  # Percentage of threshold reached

    # Print the noise level and proximity to alarm threshold
    sys.stdout.write(f"\rCurrent Noise Level: {rms_level:.3f} | {percentage}% of threshold {'(ALARM!)' if percentage >= 100 else '            '}   ")
    sys.stdout.flush()
    
    if rms_level > THRESHOLD:
        if not check_sound_level.alarm_active:
            alarm = alarm_wave.play()
            check_sound_level.alarm_active = True
            alarm.wait_done()
            # Reset alarm after a delay
            sd.sleep(int(ALARM_DURATION * 1000))
            check_sound_level.alarm_active = False

# Initialize alarm state
check_sound_level.alarm_active = False

# Main script with proper cleanup
try:
    print("Monitoring sound levels... Press Ctrl+C to stop.")
    with sd.InputStream(callback=check_sound_level):
        while True:
            sd.sleep(100)  # Keep the stream alive, check every 100ms
except KeyboardInterrupt:
    print("\nExiting...")
finally:
    print("Stopping audio stream. Goodbye!")

