import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import tempfile
import os
from deepgram import DeepgramClient

class AudioTranscriber:
    def __init__(self):
        # Initialize Deepgram client
        api_key = os.getenv("DEEPGRAM_API_KEY")
        if not api_key:
             raise ValueError("Missing DEEPGRAM_API_KEY in .env")
        self.client = DeepgramClient(api_key=api_key)

    def record_audio(self, duration=10, sample_rate=44100):
        """
        Record audio from the microphone for a fixed duration.
        Returns the path to the temporary WAV file.
        """
        print(f"🎤 Recording for {duration} seconds... (Speak now!)")
        
        recording = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1)
        sd.wait()  # Wait until recording is finished
        
        print("✅ Recording finished.")
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
            wav.write(temp_audio.name, sample_rate, recording)
            return temp_audio.name

    def transcribe_bytes(self, buffer_data):
        """
        Transcribes audio bytes directly.
        """
        print("📝 Transcribing bytes with Deepgram...")
        
        # v5.x: Pass bytes as 'request' kwarg, and options as kwargs
        response = self.client.listen.v1.media.transcribe_file(
            request=buffer_data, 
            model="nova-2", 
            smart_format=True, 
            language="en"
        )
        
        transcript = response.results.channels[0].alternatives[0].transcript
        return transcript

    def generate_speech(self, text):
        """
        Generates speech from text using Deepgram Aura (TTS).
        Returns raw audio bytes (mp3).
        """
        print(f"🗣️ Generating speech for: {text[:50]}...")
        # Deepgram TTS (Aura)
        SPEAK_OPTIONS = {"text": text}
        # Model: aura-asteria-en (Female) or aura-orion-en (Male)
        # Using Asteria for a friendly assistant voice
        options = {
            "model": "aura-asteria-en",
            "encoding": "mp3",
        }
        
        # Save to a temporary file is standard, but keeping in memory is better for Streamlit
        # Deepgram SDK .save method saves to file. 
        # We can use .stream? Or just save to temp and read back.
        
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_tts:
             filename = temp_tts.name
        
        # self.client.speak.v("1").save... failed (attribute error).
        # We found self.client.speak.v1.audio.generate exists.
        
        response = self.client.speak.v1.audio.generate(SPEAK_OPTIONS, options)
        
        # Check if response handles saving (SDK wrapper) or if we need to write bytes
        if hasattr(response, "save"):
            response.save(filename)
        elif hasattr(response, "content"):
            with open(filename, "wb") as f:
                f.write(response.content)
        else:
            # Assume it is bytes directly
            with open(filename, "wb") as f:
                f.write(response)
        
        with open(filename, "rb") as f:
            audio_bytes = f.read()
            
        os.remove(filename) # Clean up
        return audio_bytes

    def transcribe(self, audio_path):
        """
        Transcribes the audio file using Deepgram.
        """
        print("📝 Transcribing with Deepgram...")
        with open(audio_path, "rb") as audio:
             buffer_data = audio.read()
        return self.transcribe_bytes(buffer_data)

    def cleanup(self, audio_path):
        if os.path.exists(audio_path):
            os.remove(audio_path)
