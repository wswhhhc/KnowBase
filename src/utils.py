"""工具函数"""

import os
import tempfile
from pathlib import Path


def save_uploaded_file(uploaded_file) -> str:
    """保存上传文件到临时目录，返回文件路径"""
    tmp_dir = Path(tempfile.gettempdir()) / "knowbase_uploads"
    tmp_dir.mkdir(exist_ok=True)

    file_path = tmp_dir / uploaded_file.name
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
