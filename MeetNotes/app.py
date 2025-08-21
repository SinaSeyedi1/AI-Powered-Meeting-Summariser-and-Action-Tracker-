import os, io, json, datetime as dt, tempfile
import streamlit as st
import pandas as pd

from db import (
    init_db, insert_meeting, insert_actions, list_meetings, get_meeting, get_actions,
    update_action_status, delete_meeting, get_db_path
)
from services.transcribe import transcribe_local_faster_whisper
from services.summarize import summarize_ollama

# ---------- App setup ----------
st.set_page_config(page_title="AI Powered Meeting Summariser and Action Tracker", layout="wide")
APP_TITLE = "AI Powered Meeting Summariser and Action Tracker"
st.title(APP_TITLE)

# ---------- Session state helpers ----------
def _init_state():
    defaults = dict(
        transcript="", duration=0, summary="", decisions=[], actions=[],
        model_used="", last_saved_meeting_id=None
    )
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

def _clear_state():
    st.session_state.transcript = ""
    st.session_state.duration = 0
    st.session_state.summary = ""
    st.session_state.decisions = []
    st.session_state.actions = []
    st.session_state.model_used = ""
    st.session_state.last_saved_meeting_id = None

_init_state()
init_db()

# ---------- Sidebar ----------
with st.sidebar:
    st.header("Settings")
    st.caption("AI Powered Meeting Summariser and Action Tracker")
    ollama_model = st.text_input("Ollama model", value=os.getenv("OLLAMA_MODEL","mistral"))
    meeting_title = st.text_input("Meeting Title", value="")
    meeting_date = st.date_input("Meeting Date", value=dt.date.today(), format="DD/MM/YYYY")

tab1, tab2, tab3 = st.tabs(["New Meeting", "Meetings", "Help"])

# ---------- New Meeting ----------
with tab1:
    st.subheader("Upload audio/video to transcribe")
    uploaded = st.file_uploader(
        "Upload a file (mp3, mp4, wav, m4a, aac, ogg, flac)",
        type=["mp3","mp4","wav","m4a","aac","ogg","flac"],
        key="uploader",
    )
    if uploaded is not None:
        st.audio(uploaded.getvalue())

    # Run pipeline; persist results in session_state so they survive reruns
    if st.button("Transcribe and Summarise", type="primary", key="btn_transcribe"):
        if uploaded is None:
            st.warning("Please upload an audio/video file first.")
        else:
            file_bytes = uploaded.getvalue()
            try:
                with st.spinner("Transcribing..."):
                    transcript, duration = transcribe_local_faster_whisper(file_bytes)  # forced 'base' inside
                    st.session_state.transcript = transcript
                    st.session_state.duration = duration
                    st.session_state.model_used = "faster-whisper:base"

                with st.spinner("Summarising..."):
                    data = summarize_ollama(st.session_state.transcript, model=ollama_model)

                    # ---- Normalize types from LLM ----
                    sum_raw = data.get("summary", "")
                    if isinstance(sum_raw, list):
                        st.session_state.summary = [str(s).strip() for s in sum_raw if str(s).strip()]
                    else:
                        st.session_state.summary = str(sum_raw).strip()

                    dec_raw = data.get("decisions", []) or []
                    st.session_state.decisions = [
                        str(d).strip() for d in (dec_raw if isinstance(dec_raw, list) else [dec_raw]) if str(d).strip()
                    ]

                    act_raw = data.get("actions", []) or []
                    norm_actions = []
                    for a in (act_raw if isinstance(act_raw, list) else []):
                        if isinstance(a, dict):
                            norm_actions.append({
                                "owner": a.get("owner") or "TBD",
                                "text": a.get("text") or "",
                                "due_date": a.get("due_date") or None,
                                "status": a.get("status") or "open",
                            })
                        else:
                            norm_actions.append({"owner": "TBD", "text": str(a), "due_date": None, "status": "open"})
                    st.session_state.actions = norm_actions

                    st.session_state.model_used += f" + ollama:{ollama_model}"
            except Exception as e:
                st.error(f"Error: {e}")

    # Render persisted results (won't disappear after Save)
    if st.session_state.transcript:
        st.success("Transcript is ready. You can save to Meetings anytime.")
        st.text_area("Transcript", st.session_state.transcript, height=220, key="ta_transcript")

        st.subheader("Summary")
        if isinstance(st.session_state.summary, list):
            for s in st.session_state.summary:
                st.markdown(f"- {s}")
        else:
            st.markdown(st.session_state.summary or "_No summary produced._")

        st.subheader("Decisions")
        if st.session_state.decisions:
            for d in st.session_state.decisions:
                st.markdown(f"- {d}")
        else:
            st.markdown("_No explicit decisions found._")

        st.subheader("Action Items")
        if st.session_state.actions:
            st.dataframe(pd.DataFrame(st.session_state.actions))
        else:
            st.markdown("_No action items found._")

        # Save uses session_state values; UI stays intact after click
        if st.button("Save to Meetings", key="btn_save"):
            try:
                # Convert to DB-safe types
                summary_for_db = (
                    "\n".join(f"- {s}" for s in st.session_state.summary)
                    if isinstance(st.session_state.summary, list)
                    else (st.session_state.summary or "")
                )
                decisions_for_db = json.dumps(st.session_state.decisions or [], ensure_ascii=False)

                mid = insert_meeting(
                    meeting_title,
                    str(meeting_date),
                    int(st.session_state.duration or 0),
                    st.session_state.transcript,
                    summary_for_db,
                    decisions_for_db,
                    st.session_state.model_used or f"faster-whisper:base + ollama:{ollama_model}",
                )
                insert_actions(mid, st.session_state.actions or [])
                st.session_state.last_saved_meeting_id = mid
                st.success(f"Saved meeting #{mid}. Open the 'Meetings' tab to view it.")
            except Exception as e:
                st.error(f"Failed to save: {e}")
    else:
        st.info("Upload a file and click **Transcribe and Summarise** to begin.")

# ---------- Meetings ----------
with tab2:
    st.subheader("Saved Meetings")
    rows = list_meetings()
    if not rows:
        st.info("No meetings yet. Add one in the 'New Meeting' tab.")
    else:
        options = [(r["id"], f"#{r['id']} • {r['title']} • {r['meeting_date']} • {r['model_used']}") for r in rows]
        default_idx = 0
        if st.session_state.last_saved_meeting_id is not None:
            for i, (mid, _) in enumerate(options):
                if mid == st.session_state.last_saved_meeting_id:
                    default_idx = i
                    break
        selected = st.selectbox("Select a meeting", options=options, index=default_idx, format_func=lambda x: x[1])
        meeting_id = selected[0]
        rec = get_meeting(meeting_id)
        st.markdown(f"### {rec['title']} — {rec['meeting_date']}")
        st.caption(f"Duration: {rec['duration_sec']} sec • Model: {rec['model_used']}")

        st.markdown("#### Summary")
        st.markdown(rec["summary"] or "_(empty)_")

        st.markdown("#### Decisions")
        try:
            dec = json.loads(rec["decisions"]) if rec["decisions"] else []
        except Exception:
            dec = []
        st.markdown("\n".join([f"- {d}" for d in dec]) if dec else "_(none)_")

        st.markdown("#### Actions")
        acts = get_actions(meeting_id)
        if acts:
            action_df = pd.DataFrame([dict(a) for a in acts])
            st.dataframe(action_df[["id","owner","text","due_date","status"]])
            st.markdown("Update Action Status")
            action_id = st.number_input("Action ID", value=int(acts[0]["id"]), step=1)
            new_status = st.selectbox("Status", ["open","done","blocked","cancelled"], index=0)
            if st.button("Update"):
                update_action_status(int(action_id), new_status)
                st.success("Updated. Re-select meeting to refresh.")
        else:
            st.markdown("_(no actions)_")

        st.markdown("---")
        st.subheader("Export")
        include_trans = st.checkbox("Include transcript in export", value=True, key="export_inc_trans")
        if st.button("Generate Markdown"):
            md = f"# {rec['title']} ({rec['meeting_date']})\n\n"
            md += f"**Duration:** {rec['duration_sec']} sec\n\n"
            md += "## Summary\n" + (rec['summary'] or "_(empty)_") + "\n\n"
            md += "## Decisions\n" + ("\n".join([f"- {d}" for d in dec]) if dec else "_(none)_") + "\n\n"
            if acts:
                md += "## Action Items\n"
                for a in acts:
                    md += f"- [{a['status']}] {a['owner'] or 'TBD'}: {a['text']} (due: {a['due_date'] or 'TBD'})\n"
                md += "\n"
            if include_trans:
                md += "## Transcript\n" + (rec["transcript"] or "")
            st.download_button("Download .md", data=md.encode("utf-8"), file_name=f"meeting_{meeting_id}.md", mime="text/markdown")

        st.markdown("---")
        st.subheader("Delete Meeting")
        if st.button("Delete this meeting"):
            delete_meeting(meeting_id)
            st.warning("Deleted. Refresh or re-open the Meetings tab.")

# ---------- Help ----------
with tab3:
    st.markdown(
    """
    ### How to Use This App

    1. **Upload your meeting recording** (MP3, WAV, MP4 up to 2 GB).
    2. The app will transcribe the meeting using speech-to-text.
    3. Click Summarise to generate:
       - Concise meeting summary  
       - Key decisions made  
       - Action items with owners and deadlines  
    4. Click **Save to Meetings** to store results in the database.  
    5. View past meetings anytime under **Meeting History**.  

    Tips  
    - Clear audio gives better results.  
    - Long meetings may take more time.  
    - Action items can be updated later.  

    ---

    ### How to Run Locally

    1. Install ffmpeg  
       - Windows: winget install ffmpeg  

    2. Install dependencies:  
    ```
    pip install -r requirements.txt
    ```

    3. Make sure Ollama is running and the model is present:  
    ```
    ollama pull mistral
    ```

    4. Start the app:  
    ```
    streamlit run app.py
    ```
    """
    )





