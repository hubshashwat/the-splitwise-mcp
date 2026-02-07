
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import os
import time
from dotenv import load_dotenv
from deepgram import DeepgramClient

load_dotenv()

def debug_audio():
    print("📋 Listing Audio Devices:")
    print(sd.query_devices())
    
    duration = 5
    fs = 44100
    
    print(f"\n🎤 Recording for {duration} seconds... PLEASE SPEAK!")
    recording = sd.rec(int(duration * fs), samplerate=fs, channels=1)
    sd.wait()
    print("✅ Recording finished.")
    
    # Calculate volume
    rms = np.sqrt(np.mean(recording**2))
    print(f"📊 Audio RMS (Volume): {rms}")
    
    if rms < 0.001:
        print("⚠️  WARNING: Audio seems silent! Check your microphone input settings.")
    else:
        print("🔊 Audio detected.")
        
    filename = "debug_output.wav"
    wav.write(filename, fs, recording)
    print(f"💾 Saved to {filename}")
    
    # Try transcription
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        print("❌ No Deepgram API Key found.")
        return

    try:
        dg = DeepgramClient(api_key=api_key)
        with open(filename, "rb") as audio:
            buffer_data = audio.read()
            
        print("📝 Sending to Deepgram...")
        options = {"model": "nova-2", "smart_format": True, "language": "en"}
        
        # Note: adjust this call based on what I saw in audio.py
        response = dg.listen.v1.media.transcribe_file(
            request=buffer_data, 
            model="nova-2", 
            smart_format=True, 
            language="en"
        )
        # Verify response structure specific to the SDK version used in audio.py
        # Actually audio.py used: client.listen.v1.media.transcribe_file(request=buffer_data, ...)
        # Let's try to match audio.py exactly first
        
        print("\n--- Raw Response Summary ---")
        print(response.to_json() if hasattr(response, 'to_json') else response)
        
        transcript = response.results.channels[0].alternatives[0].transcript
        print(f"\n🗣️  Transcript: '{transcript}'")
        
    except Exception as e:
        print(f"\n❌ Deepgram Error: {e}")
        # specific fallback for different SDK versions if needed
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_audio()
