#!/usr/bin/env python3
"""model_llm.py — LLM 接口（本地 Ollama 优先，云端 DeepSeek 降级）

"规则算，LLM 讲"：计算层零 token 确定性，LLM 只做解释/总结。
模型切换由 config/model_config.json 的 active 控制。

用法:
  from core.model_llm import llm_generate
  text = llm_generate("生成决策总结报告...", temperature=0.3, max_tokens=500)
"""

import json
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load_config():
    path = os.path.join(_PROJECT_ROOT, "config", "model_config.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"active": "local_ollama", "models": {}}


def _call_openai(base_url, model, api_key, prompt, temperature, max_tokens):
    """OpenAI 兼容接口调用（本地 Ollama / 云端 DeepSeek 通用）。"""
    import urllib.request
    url = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            msg = data["choices"][0]["message"]
            content = (msg.get("content") or "").strip()
            if not content:
                content = (msg.get("reasoning") or "").strip()  # 推理模型 ornith 内容在 reasoning
            return content or None
    except Exception:
        return None


def llm_generate(prompt: str, temperature: float = 0.1, max_tokens: int = 200) -> str:
    """调用当前激活模型生成文本。本地 Ollama 优先，云端 DeepSeek 降级。
    全部失败返回 '[模型不可用]'（不抛异常，决策流不中断）。"""
    cfg = _load_config()
    active = cfg.get("active", "local_ollama")
    models = cfg.get("models", {})
    order = [active] + [k for k in models if k != active]  # 当前激活优先，其余降级
    for name in order:
        m = models.get(name)
        if not m or not m.get("base_url"):
            continue
        try:
            out = _call_openai(m["base_url"], m.get("model"), m.get("api_key", ""),
                               prompt, temperature, max_tokens)
            if out:
                return out
        except Exception:
            continue
    return "[模型不可用]"


if __name__ == "__main__":
    print(llm_generate("用一句话说明补货决策的含义。", temperature=0.1, max_tokens=50))
