import streamlit as st
st.set_page_config(page_title="Legal Assistant")

import base64
import json
import os
import uuid
import tempfile
from datetime import datetime
import io

from dotenv import load_dotenv
from openai import OpenAI


AUDIO_RECORDER_AVAILABLE = True


import multimodal_engine as engine

load_dotenv()
oclient = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


st.title("Legal Assistant")
st.markdown("Ask a legal question below or describe an incident.")


if "history" not in st.session_state:
    st.session_state.history = []

if "temp_case_id" not in st.session_state:
    date_str = datetime.now().strftime("%Y%m%d")
    st.session_state.temp_case_id = f"temp_{date_str}_{uuid.uuid4().hex[:6]}"

if "processed_audio_ids" not in st.session_state:
    st.session_state.processed_audio_ids = set()


def strip_json_from_reply(reply: str) -> str:
    try:
        
        json_start = reply.find("{")
        json_end = reply.rfind("}") + 1
        
        if json_start != -1 and json_end > json_start:
           
            before_json = reply[:json_start].strip()
            after_json = reply[json_end:].strip()
            
           
            if before_json and after_json:
                clean_reply = f"{before_json} {after_json}".strip()
            elif before_json:
                clean_reply = before_json
            elif after_json:
                clean_reply = after_json
            else:
                clean_reply = ""
            
            
            if clean_reply:
                return clean_reply
        
       
        original = reply.strip()
        if original.startswith("{") and original.endswith("}"):
           
            return "I've recorded your case information. How else can I help you?"
        
        return original if original else "I've processed your request."
        
    except Exception:
        return reply.strip() if reply.strip() else "I apologize, but I couldn't generate a proper response."

def maybe_store_case(reply: str):
    try:
        s = reply
        j0 = s.find("{")
        j1 = s.rfind("}") + 1
        if j0 != -1 and j1 != -1:
            json_block = s[j0:j1]
            print(f"DEBUG: Found JSON block: {json_block}")
            
           
            try:
                import json
                from datetime import datetime, timedelta
                
                parsed = json.loads(json_block)
                print(f"DEBUG: JSON is valid: {parsed}")
                
                
                cleaned_data = {}
                
                
                if "Case Type" in parsed:
                    cleaned_data["Case Type"] = parsed["Case Type"]
                
               
                if "Description" in parsed:
                    cleaned_data["Description"] = parsed["Description"]
                
                
                if "Date of Incident" in parsed:
                    date_str = parsed["Date of Incident"].lower().strip()
                    try:
                        if date_str in ["yesterday"]:
                            actual_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                            cleaned_data["Date of Incident"] = actual_date
                        elif date_str in ["today"]:
                            actual_date = datetime.now().strftime("%Y-%m-%d")
                            cleaned_data["Date of Incident"] = actual_date
                        elif "ago" in date_str:
                            
                            if "couple" in date_str or "few" in date_str:
                                actual_date = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
                            else:
                                
                                actual_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                            cleaned_data["Date of Incident"] = actual_date
                        else:
                            
                            try:
                                
                                for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y"]:
                                    try:
                                        datetime.strptime(date_str, fmt)
                                        cleaned_data["Date of Incident"] = date_str
                                        break
                                    except ValueError:
                                        continue
                                else:
                                    
                                    cleaned_data["Date of Incident"] = datetime.now().strftime("%Y-%m-%d")
                            except:
                                cleaned_data["Date of Incident"] = datetime.now().strftime("%Y-%m-%d")
                    except Exception as e:
                        print(f"DEBUG: Date parsing error: {e}")
                        
                        cleaned_data["Date of Incident"] = datetime.now().strftime("%Y-%m-%d")
                
                
                required_fields = ["Full Name", "Phone Number", "Email"]
                for field in required_fields:
                    if field in parsed:
                        cleaned_data[field] = parsed[field]
                    else:
                        
                        cleaned_data[field] = ""
                
                
                cleaned_json = json.dumps(cleaned_data)
                print(f"DEBUG: Cleaned JSON: {cleaned_json}")
                st.write(f"DEBUG: Saving cleaned data: {cleaned_json}")
                
                
                result = engine.handle_case_storage(cleaned_json)
                print(f"DEBUG: Storage result: {result}")
                
                if result:
                    st.success("Case information saved successfully!")
                else:
                    st.warning("Case information could not be saved - check database connection")
                    
            except json.JSONDecodeError as e:
                print(f"DEBUG: Invalid JSON format: {e}")
                st.error(f"Invalid JSON format: {e}")
                
    except Exception as e:
        print(f"DEBUG: Error in maybe_store_case: {e}")
        st.error(f"Error saving case info: {e}")

def transcribe_audio(audio_bytes):
    try:
        
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"  
        
        
        transcript = oclient.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file
        )
        
        return transcript.text.strip()
        
    except Exception as e:
        st.error(f"Transcription error: {e}")
        return ""

def text_to_speech(text):
    try:
        
        if not text or not text.strip():
            text = "I apologize, but I couldn't generate a proper response."
        
        
        if len(text) > 4000:
            text = text[:4000] + "..."
        
        response = oclient.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text.strip(),
            response_format="mp3"
        )
        return response.content
    except Exception as e:
        st.error(f"TTS error: {e}")
        return None

def process_user_input(user_input, is_voice=False):
    st.session_state.history.append(("user", user_input))

    with st.spinner("Thinking..."):
        reply = engine.chat(user_input, session_id=st.session_state.temp_case_id)
        print(f"DEBUG: Full bot reply: {repr(reply)}")
        maybe_store_case(reply)

        clean_reply = strip_json_from_reply(reply)
        if not clean_reply.strip():
            clean_reply = "I recieved your message and I'm processing it."

        st.session_state.history.append(("assistant", clean_reply))

        if is_voice:
            with st.spinner("Generating voice response..."):
                audio_response = text_to_speech(clean_reply)
                if audio_response:
                    st.audio(audio_response, format="audio/mp3", autoplay=True)
    
    


user_text = st.chat_input("Type your message here...")
if user_text:
    process_user_input(user_text, is_voice=False)


for role, message in st.session_state.history:
    with st.chat_message(role):
        if role == "assistant":
            clean_message = strip_json_from_reply(message)
            st.markdown(clean_message)
        else:
            st.write(message)

st.markdown("---")


st.subheader("Voice Input")

if AUDIO_RECORDER_AVAILABLE:
    st.markdown("**Record your voice message:**")
    
    
    audio_bytes = st.audio_input("Record your question", label_visibility="collapsed")
    
    if audio_bytes is not None:
        
        audio_id = hash(audio_bytes.read())
        audio_bytes.seek(0) 
        
        if audio_id not in st.session_state.processed_audio_ids:
            st.session_state.processed_audio_ids.add(audio_id)
            
            st.audio(audio_bytes, format="audio/wav")
            
            
            with st.spinner("Processing your voice..."):
                audio_data = audio_bytes.read()
                transcript = transcribe_audio(audio_data)
                
                if transcript:
                    st.success(f"Heard: '{transcript}'")
                    process_user_input(transcript, is_voice=True)
                else:
                    st.error("Could not understand the audio. Please try again.")
        else:
            
            st.audio(audio_bytes, format="audio/wav")
            st.info("This audio has already been processed.")

else:
    
    st.error("Audio input not available in this Streamlit version")
    
    
    st.markdown("**Alternative: Upload an audio file**")
    uploaded_file = st.file_uploader("Choose an audio file", type=['wav', 'mp3', 'm4a'])
    
    if uploaded_file is not None:
        st.audio(uploaded_file, format="audio/wav")
        
        if st.button("Transcribe & Send"):
            with st.spinner("Processing uploaded audio..."):
                audio_bytes = uploaded_file.read()
                transcript = transcribe_audio(audio_bytes)
                
                if transcript:
                    st.success(f"Transcribed: '{transcript}'")
                    process_user_input(transcript, is_voice=True)
                else:
                    st.error("Could not transcribe the audio file.")

