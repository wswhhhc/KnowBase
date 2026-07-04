"""联网搜索模块 — 基于 Tavily API。"""

from src.config.constants import TAVILY_API_KEY
from src.config.runtime_overrides import _is_configured_api_key, get_runtime_setting


def web_search(query: str, max_results: int = 5) -> tuple[list[dict], str]:
    """使用 Tavily 搜索网络，返回结构化结果列表和错误信息。

    每项结果包含：title, url, content, score
    """
    api_key = get_runtime_setting("tavily_api_key", TAVILY_API_KEY)
    if not _is_configured_api_key(api_key):
        return [], "未配置 TAVILY_API_KEY。"

    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=True,
        )
        results = []
        for item in response.get("results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "score": item.get("score", 0.0),
            })
        return results, ""
    except Exception as exc:
        return [], f"联网搜索失败：{exc}"


def format_search_results(results: list[dict]) -> str:
    """将搜索格式化为 LLM 上下文文本。"""
    if not results:
        return ""
    parts = ["以下是从网络搜索到的相关信息：\n"]
    for i, item in enumerate(results, 1):
        parts.append(
            f"[网络来源 {i}] {item['title']}\n"
            f"链接：{item['url']}\n"
            f"内容：{item['content']}\n"
        )
    return "\n".join(parts)
