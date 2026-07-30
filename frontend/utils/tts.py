from gtts import gTTS
from io import BytesIO


def speak_text(text):
    """Return MP3 bytes for the given text (or None on error/empty).

    The frontend will use `st.audio()` to play these bytes inline instead of
    saving a temporary file to disk.
    """
    if not text or not str(text).strip():
        return None

    try:
        fp = BytesIO()
        tts = gTTS(text=text, lang="en")
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp.read()
    except Exception:
        return None
