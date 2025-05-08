import requests
import pyttsx3
import re
import os
import random
from google.cloud import speech
import pyaudio
from six.moves import queue

# ESP8266 server URLs
ESP8266_LED_URL = "http://192.168.1.102/LED"#（自分のIPにへんこうして）
ESP8266_FAN_URL = "http://192.168.1.102/fanControl"#（自分のIPにへんこうして）
ESP8266_TEMP_URL = "http://192.168.1.102/getData"  # URL to get temperature（自分のIPにへんこうして）

# Google Speech-to-Text credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "C:\\Users\\kanat\\Downloads\\key.json"

# TTS Engine
tts_engine = pyttsx3.init()

# Ensure TTS uses English language
voices = tts_engine.getProperty('voices')
for voice in voices:
    if 'english' in voice.name.lower():
        tts_engine.setProperty('voice', voice.id)
        break

def speak(text):
    """Text-to-speech module"""
    tts_engine.say(text)
    tts_engine.runAndWait()

# Audio parameters
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms

class MicrophoneStream:
    """Handles audio input from microphone"""
    def __init__(self, rate, chunk):
        self.rate = rate
        self.chunk = chunk
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        self.audio_interface = pyaudio.PyAudio()
        self.audio_stream = self.audio_interface.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk,
            stream_callback=self._fill_buffer,
        )
        self.closed = False
        return self

    def __exit__(self, type, value, traceback):
        self.audio_stream.stop_stream()
        self.audio_stream.close()
        self.closed = True
        self.audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b"".join(data)

def listen_and_recognize():
    """Listen to microphone and recognize speech"""
    client = speech.SpeechClient()
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code="en-US",
    )
    streaming_config = speech.StreamingRecognitionConfig(
        config=config, interim_results=False
    )

    with MicrophoneStream(RATE, CHUNK) as stream:
        audio_generator = stream.generator()
        requests = (speech.StreamingRecognizeRequest(audio_content=content)
                    for content in audio_generator)

        responses = client.streaming_recognize(streaming_config, requests)

        for response in responses:
            if response.results and response.results[0].is_final:
                return response.results[0].alternatives[0].transcript.lower().strip()

def get_temperature():
    """Fetch temperature data from ESP8266"""
    try:
        response = requests.get(ESP8266_TEMP_URL)
        if response.status_code == 200:
            data = response.json()
            temperature = data.get("temperature")
            if temperature is not None:
                # Use English for temperature announcement
                speak(f"The current temperature is {temperature} degrees Celsius.")
                print(f"Temperature: {temperature}°C")
            else:
                speak("Failed to get temperature data.")
        else:
            speak("Failed to connect to the temperature server.")
    except requests.exceptions.RequestException as e:
        speak("Failed to fetch the temperature data.")
        print(f"Request error: {e}")

def control_device(command):
    """Control devices based on command"""
    try:
        if "light" in command:
            if "on" in command:
                requests.post(ESP8266_LED_URL, data={"action": "on"})
                speak("The light has been turned on.")
            elif "off" in command:
                requests.post(ESP8266_LED_URL, data={"action": "off"})
                speak("The light has been turned off.")
        elif "fan" in command:
            if "on" in command:
                requests.post(ESP8266_FAN_URL, data={"action": "on"})
                speak("The fan has been turned on.")
            elif "off" in command:
                requests.post(ESP8266_FAN_URL, data={"action": "off"})
                speak("The fan has been turned off.")
        elif "temperature" in command:
            get_temperature()
        else:
            speak("I couldn't recognize the device you're trying to control.")
    except requests.exceptions.RequestException as e:
        speak("Failed to control the device. Please check the network connection.")
        print(f"Request error: {e}")

def wake_up_reply():
    """Randomly select a wake-up reply"""
    replies = [
        "I'm sir. How can I help you?",
        "Wait for your command, sir.",
        "Please give me instructions."
    ]
    speak(random.choice(replies))

def main():
    speak("Welcome to the smart home assistant. Say 'hello', 'hi', or 'jarvis' to wake me up.")
    is_awake = False

    while True:
        print("Listening...")
        command = listen_and_recognize()

        if command:
            print(f"Recognized: {command}")
            if not is_awake:
                if "hello" in command or "hi" in command or "jarvis" in command:
                    is_awake = True
                    wake_up_reply()  # Say a random reply after waking up
                else:
                    print("Assistant is sleeping. Say 'hello', 'hi', or 'jarvis' to wake up.")
            else:
                if "exit" in command:
                    speak("Goodbye, sir.")
                    break
                elif "sleep" in command:
                    is_awake = False
                    speak("Going to sleep. Say 'hello', 'hi', or 'jarvis' to wake me up.")
                elif "goodbye" in command:
                    speak("Goodbye, sir.")
                    break
                else:
                    control_device(command)

if __name__ == "__main__":
    main()
