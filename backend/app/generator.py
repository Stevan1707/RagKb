"""拼 prompt + 调大模型（非流式）。

只用标准库发 HTTP 请求，不绑定任何厂商 SDK：只要对方兼容 OpenAI 的
/v1/chat/completions，改 .env 里的三个变量就能切换（Ollama / DeepSeek / 通义）。

为什么不做流式：一次拿完整答案，代码只有"发请求 → 解析 JSON"两步，
不用处理事件流、半包、断连。代价是页面要等几秒。
"""

import asyncio
import json
import urllib.error
import urllib.request
from typing import Iterable

from app.config import settings
from app.retrieval import Hit

SYSTEM_PROMPT = """你是一个严谨的个人知识库助手。请遵守：
1. 只依据【资料】里的内容回答，不要使用资料以外的知识，也不要编造。
2. 每个结论后面用 [编号] 标注来源，编号对应资料序号，例如「宪法第三十五条规定……[1]」。
3. 如果资料不足以回答，直接说「根据现有资料无法确定」，并说明缺什么信息。
4. 用中文回答，控制在 300 字以内，不要复述资料原文。"""


class LLMError(RuntimeError):
    """调用大模型失败：连不上、鉴权错、返回体异常。"""


def build_context(hits: Iterable[Hit]) -> str:
    """把检索结果拼成带编号的资料块，编号与前端 sources 的 rank 对应。"""
    return "\n\n".join(
        f"[{rank}] 《{hit.doc_name}》 第 {hit.page} 页\n{hit.content}"
        for rank, hit in enumerate(hits, start=1)
    )


def build_messages(
    question: str,
    hits: list[Hit],
    history: list[dict] | None = None,
) -> list[dict]:
    """组装 OpenAI 风格的 messages：system + 历史 + 资料 + 本轮问题。"""
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    for item in history or []:
        role = item.get("role")
        content = (item.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    if hits:
        user_content = (
            f"【资料】\n{build_context(hits)}\n\n"
            f"【问题】\n{question}\n\n"
            "请依据上面的资料回答，并按 [编号] 标注引用。"
        )
    else:
        # 没检索到资料时也要如实告诉模型，避免它自由发挥
        user_content = (
            "【资料】\n（没有检索到相关资料）\n\n"
            f"【问题】\n{question}\n\n"
            "资料为空，请直接说明知识库中没有相关内容，不要凭常识作答。"
        )

    messages.append({"role": "user", "content": user_content})
    return messages


def _post_completion(messages: list[dict]) -> str:
    """同步发一次请求，返回完整回答（在 complete() 里丢进线程池）。"""
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
        "stream": False,
    }
    # 思考型模型会先用掉一大半 max_tokens 做推理，正文可能是空的。
    # Ollama 认这个字段；换厂商不认识时会忽略，所以不影响通用性。
    if settings.llm_reasoning_effort:
        payload["reasoning_effort"] = settings.llm_reasoning_effort
    request = urllib.request.Request(
        settings.llm_chat_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.llm_api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.llm_timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:300]
        raise LLMError(f"大模型返回 HTTP {exc.code}：{detail}") from exc
    except urllib.error.URLError as exc:
        raise LLMError(
            f"连不上大模型接口 {settings.llm_base_url}（Ollama 启动了吗？）：{exc.reason}"
        ) from exc

    choices = body.get("choices") or []
    if not choices:
        raise LLMError(f"返回体里没有 choices：{str(body)[:300]}")

    content = ((choices[0].get("message") or {}).get("content") or "").strip()
    if not content:
        raise LLMError("大模型返回了空内容")
    return content


async def complete(messages: list[dict]) -> str:
    """异步入口：把阻塞的 HTTP 调用放进线程池，不堵事件循环。"""
    return await asyncio.to_thread(_post_completion, messages)
