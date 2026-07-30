import tempfile
import os


def save_upload_file(upload_file, suffix=".pdf"):
    """
    Saves FastAPI UploadFile to a temporary file and returns the path.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(upload_file)
        return temp_file.name


def delete_file(path: str):
    """
    Deletes a file safely if it exists.
    """
    if path and os.path.exists(path):
        os.remove(path)