Multimodal_AI_Chatbot

This project is a multimodal legal intake bot built with Streamlit and OpenAI. It handles both text and voice, extracts client information, and saves everything to Postgres. The goal is to make legal intake conversational, not robotic.

A demo video is included in the repository showing how the assistant works in real time - switching between text and voice, capturing client details naturally, and storing them in the database.

What It Does
It lets a user type or speak, and the assistant figures out what they’re saying like who they are, what happened, when, and how to contact them. Whisper converts speech to text, GPT handles the reasoning and field extraction, and TTS gives the voice response. Every complete case gets saved to Postgres automatically.

Demo Video  
A short walkthrough showing real-time text and voice intake, natural follow-up questions, and automatic case storage.



[https://youtu.be/kSthdrNsfvI?si=2-URNKoSMylq4qGL](https://github.com/user-attachments/assets/2d468422-18b9-4367-b4e2-8d199a37e0b6)



How It’s Structured
Multimodal_interface.py is the UI. It runs the Streamlit chat, handles text and audio input, and plays back the assistant’s TTS reply. It strips out JSON fields before showing messages, so the user only sees the clean conversation.
Multimodal_engine.py is the brain. It extracts fields like name, contact, date, and description. It keeps track of what’s already known, asks for just one missing detail at a time, normalizes relative dates like “last Friday” into actual dates, and writes to the database.

Tech Stack
Python
Streamlit
OpenAI (GPT-4 for chat, Whisper-1 for speech-to-text, TTS-1 for voice)
PostgreSQL
Dateparser

Setup
To run the project, install the dependencies, set your OpenAI API key, and make sure Postgres is running. Then start the Streamlit app and begin a conversation with the assistant.

How It Feels
You open the app and just start talking. “I was in an accident last Tuesday.” It understands that, asks what’s missing, and once all details are filled, it logs the case quietly in the background. It can also speak back if you want, making it feel like a real assistant, not a form.


Technical Deep Dive  
A blog post explaining the conversational state tracking, voice handling, incremental field extraction, and database design behind this system.

https://medium.com/@sidgajraj/the-age-of-multimodal-intelligence-when-ai-learns-to-listen-think-and-speak-40552fd9d303

Key Functions
Strip_json_from_reply removes structured data before display
Maybe_store_case catches JSON and stores it
Parse_incident_date turns relative phrasing into real dates
Save_case writes to Postgres

Future Ideas
Add phone and email validation
Build a dashboard to browse stored cases
Add authentication and role-based access
Connect to CRM via API
Measure prompt accuracy and completion rates

Why It Matters
Law firms spend hours collecting client info. This turns that into minutes. The system asks questions naturally, keeps the tone human, and stores everything in a structured database. It’s fast, clean, and human.
