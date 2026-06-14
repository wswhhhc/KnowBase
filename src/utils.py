"""工具函数"""

import tempfile
from pathlib import Path

from config.settings import MAX_UPLOAD_MB


ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".md"}


def sanitize_upload_filename(filename: str) -> str:
    """Return a safe display/storage filename for an uploaded file."""
    normalized = filename.replace("\\", "/")
    name = Path(normalized).name.strip()
    if not name or name in {".", ".."}:
        raise ValueError("上传文件名无效。")
    return name


def validate_upload(uploaded_file, max_upload_mb: int = MAX_UPLOAD_MB) -> str:
    """Validate size and extension, returning the sanitized filename."""
    safe_name = sanitize_upload_filename(uploaded_file.name)
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValueError("仅支持 .txt 和 .md 文件。")

    size = getattr(uploaded_file, "size", None)
    if size is not None and size > max_upload_mb * 1024 * 1024:
        raise ValueError(f"文件不能超过 {max_upload_mb} MB。")

    return safe_name


def save_uploaded_file(uploaded_file) -> str:
    """保存上传文件到临时目录，返回文件路径"""
    tmp_dir = Path(tempfile.gettempdir()) / "knowbase_uploads"
    tmp_dir.mkdir(exist_ok=True)

    safe_name = validate_upload(uploaded_file)
    file_path = tmp_dir / safe_name
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return str(file_path)


def format_chat_history(messages: list) -> list:
    """将 Streamlit 的 messages 格式转为 (question, answer) 列表"""
    history = []
    i = 0
    while i < len(messages):
        if messages[i]["role"] == "user":
            question = messages[i]["content"]
            answer = ""
            if i + 1 < len(messages) and messages[i + 1]["role"] == "assistant":
                answer = messages[i + 1]["content"]
            history.append((question, answer))
            i += 2
        else:
            i += 1
    return history
