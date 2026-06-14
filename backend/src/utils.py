"""工具函数"""

import json
import re
import tempfile
from pathlib import Path

from config.settings import MAX_UPLOAD_MB


ALLOWED_UPLOAD_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".html", ".htm"}


def sanitize_upload_filename(filename: str) -> str:
    """Return a safe display/storage filename for an uploaded file."""
    normalized = filename.replace("\\", "/")
    name = Path(normalized).name.strip()
    if not name or name in {".", ".."}:
        raise ValueError("上传文件名无效。")
    return name


def validate_upload(uploaded_file, max_upload_mb: int = MAX_UPLOAD_MB) -> str:
    """Validate size and extension, returning the sanitized filename.

    Handles both Streamlit's UploadedFile (.name) and FastAPI's UploadFile (.filename).
    """
    name = getattr(uploaded_file, "filename", None) or getattr(uploaded_file, "name", "")
    safe_name = sanitize_upload_filename(name)
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise ValueError("仅支持 .txt、.md、.pdf、.docx、.html 文件。")

    size = getattr(uploaded_file, "size", None)
    if size is not None and size > max_upload_mb * 1024 * 1024:
        raise ValueError(f"文件不能超过 {max_upload_mb} MB。")

    return safe_name


def save_uploaded_file(uploaded_file) -> str:
    """保存上传文件到临时目录，返回文件路径

    兼容 Streamlit UploadedFile (.getbuffer()) 和 FastAPI UploadFile (.read()).
    """
    tmp_dir = Path(tempfile.gettempdir()) / "knowbase_uploads"
    tmp_dir.mkdir(exist_ok=True)

    safe_name = validate_upload(uploaded_file)
    file_path = tmp_dir / safe_name
    data = uploaded_file.getbuffer() if hasattr(uploaded_file, "getbuffer") else uploaded_file.file.read()
    with open(file_path, "wb") as f:
        f.write(data)

    return str(file_path)


def json_from_text(text: str) -> dict:
    """从 LLM 返回文本中提取 JSON，处理 markdown 代码围栏。"""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    return json.loads(match.group(0) if match else text)


ERROR_CLASSIFICATION = {
    "authentication": ("API Key 配置有误或已失效", "请检查 .env 中的 SILICONFLOW_API_KEY"),
    "rate_limit": ("API 调用被限流", "请稍后再试"),
    "timeout": ("请求超时", "网络不稳定，请检查网络连接后重试"),
    "model": ("模型调用异常", "请检查 LLM_MODEL 配置是否有效"),
}


def classify_error(e: Exception) -> tuple[str, str]:
    """将异常分类为可读的用户提示。返回 (标题, 建议) 元组。"""
    msg = str(e).lower()
    if any(k in msg for k in ["auth", "api_key", "unauthorized", "forbidden"]):
        return ERROR_CLASSIFICATION["authentication"]
    if any(k in msg for k in ["rate", "too many", "429"]):
        return ERROR_CLASSIFICATION["rate_limit"]
    if any(k in msg for k in ["timeout", "timed out"]):
        return ERROR_CLASSIFICATION["timeout"]
    if any(k in msg for k in ["model", "not found", "404"]):
        return ERROR_CLASSIFICATION["model"]
    return ("未知错误", str(e))


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
