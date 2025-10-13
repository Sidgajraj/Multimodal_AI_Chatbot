import psycopg2
import os
import json
import re
from datetime import datetime, timedelta
import dateparser
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


_SESSIONS = {}  

def _get_session(session_id: str):
    if not session_id:
        session_id = "_default"
    if session_id not in _SESSIONS:
        _SESSIONS[session_id] = {
            "Full Name": "",
            "Contact": "",
            "Case Type": "",
            "Date of Incident": "",
            "Description": ""
        }
    return _SESSIONS[session_id]

def _reset_session(session_id: str):
    _SESSIONS[session_id] = {
        "Full Name": "",
        "Contact": "",
        "Case Type": "",
        "Date of Incident": "",
        "Description": ""
    }


def save_case(name, contact, date, description):
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="lawfirm_bot",
            user="postgres",
            password=os.getenv("POSTGRES_PASSWORD")
        )
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO intake_cases (name, contact, date_of_incident, description)
            VALUES (%s, %s, %s, %s)
        """, (name, contact, date, description))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print("Error saving case:", e)
        return False


def parse_incident_date(date_str):
    if not date_str:
        return None
    date_str = date_str.lower().strip()
    today = datetime.today()
    m = re.match(r"last (\w+)", date_str)
    if m:
        weekday_str = m.group(1).capitalize()
        weekdays = {
            "Monday": 0, "Tuesday": 1, "Wednesday": 2,
            "Thursday": 3, "Friday": 4, "Saturday": 5, "Sunday": 6
        }
        if weekday_str in weekdays:
            today_wd = today.weekday()
            target_wd = weekdays[weekday_str]
            delta = (today_wd - target_wd + 7) % 7 or 7
            return today - timedelta(days=delta)
    parsed = dateparser.parse(
        date_str,
        settings={"PREFER_DATES_FROM": "past", "RELATIVE_BASE": today}
    )
    return parsed


def _extract_delta(user_input: str) -> dict:
    prompt = f"""
Extract ONLY the fields explicitly present in the user's message.
Return a JSON object with some of these keys if present, else omit the key:
{{
  "Full Name": "...",           # full name if present
  "Contact": "...",             # phone or email if present
  "Case Type": "...",           # infer from incident if clear (Car Accident, Slip and Fall, Medical Malpractice, Personal Injury, Workers Compensation, Product Liability, Wrongful Death, Other)
  "Date of Incident": "...",    # relative or absolute phrasing exactly as user said (e.g., "yesterday", "last week", "2025-08-01")
  "Description": "..."          # one-line what happened if present
}}

User message:
\"\"\"{user_input}\"\"\""
"""
    try:
        r = client.chat.completions.create(
            model="gpt-4-0613",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0
        )
        text = r.choices[0].message.content.strip()
        j0, j1 = text.find("{"), text.rfind("}") + 1
        if j0 >= 0 and j1 > j0:
            return json.loads(text[j0:j1])
    except Exception as e:
        print("extract error:", e)
    return {}

def _merge_session(session: dict, delta: dict):
    for k, v in (delta or {}).items():
        if isinstance(v, str) and v.strip():
            session[k] = v.strip()

def _next_missing_field(session: dict) -> str:
    order = ["Description", "Date of Incident", "Full Name", "Contact"]
    for k in order:
        if not session.get(k, "").strip():
            return k
    return ""  


def _conversational_prompt(user_input: str, session_snapshot: dict, next_missing: str) -> str:
    known = json.dumps(session_snapshot, ensure_ascii=False)
    return f"""
You are a warm, concise legal intake assistant.
Remember what the user has already provided. Do NOT ask for the same info again.

KNOWN INFO (what we already have — do NOT re-ask these):
{known}

RULES:
- Keep it human and empathetic.
- Ask at most ONE follow-up, and ONLY for the NEXT missing field: {next_missing if next_missing else "none (we have all we need)"}.
- If user asks a legal question, answer briefly (not legal advice) then, if natural, ask for the next missing field.
- If user asks to talk to a human, say: You can reach our intake team at **sidgajraj@gmail.com** or **(xxx) xxx-xxxx**. I'm here if you'd like to continue now.
- Include a compact JSON block ONLY if (a) we have enough detail for multiple fields OR (b) all fields are filled. Otherwise, no JSON.
- Never ask for an item that's already present in KNOWN INFO.

User message:
\"\"\"{user_input}\"\"\""
""".strip()


def chat(user_text: str, session_id: str = None) -> str:
    try:
        session = _get_session(session_id or "_default")

        if any(kw in user_text.lower() for kw in ["start over", "restart", "reset", "new case"]):
            _reset_session(session_id or "_default")

        delta = _extract_delta(user_text)
        _merge_session(session, delta)

        nxt = _next_missing_field(session)

        prompt = _conversational_prompt(user_text, session_snapshot=session, next_missing=nxt)
        resp = client.chat.completions.create(
            model="gpt-4-0613",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        reply = resp.choices[0].message.content.strip()

        try:
            j0, j1 = reply.find("{"), reply.rfind("}") + 1
            if j0 >= 0 and j1 > j0:
                parsed = json.loads(reply[j0:j1])
                _merge_session(session, parsed)
        except Exception:
            pass

        if not _next_missing_field(session):
            parsed_date = parse_incident_date(session.get("Date of Incident", ""))
            if parsed_date:
                # CHANGED: no case_type argument
                ok = save_case(
                    name=session.get("Full Name", ""),
                    contact=session.get("Contact", ""),
                    date=parsed_date.strftime("%Y-%m-%d"),
                    description=session.get("Description", "")
                )
                if ok:
                    pass

        return reply

    except Exception as e:
        print("Engine error:", e)
        return "I’m here to help. Could you share what happened, and when it took place?"


def extract_case_info_prompt_only(user_input):
    return chat(user_input, session_id="_default")

def handle_case_storage(gpt_output):
    try:
        s = gpt_output.strip()
        j0 = s.find('{')
        if j0 == -1:
            print("No JSON found in GPT output.")
            return False
        j1 = s.rfind('}') + 1
        data = json.loads(s[j0:j1])

        parsed_date = parse_incident_date(data.get("Date of Incident", ""))
        if not parsed_date:
            print("Could not parse the date:", data.get("Date of Incident"))
            return False

        ok = save_case(
            name=data.get("Full Name", ""),
            contact=data.get("Contact", ""),
            date=parsed_date.strftime("%Y-%m-%d"),
            description=data.get("Description", "")
        )
        if ok:
            print("Case saved successfully")
        return ok
    except Exception as e:
        print("Error while saving case info:", e)
        return False
