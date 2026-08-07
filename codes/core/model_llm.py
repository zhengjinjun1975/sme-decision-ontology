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
        m = dict(models.get(name) or {})
        if not m.get("base_url"):
            continue
        # 云端 key 优先: 环境变量 DEEPSEEK_API_KEY(权威来源, 不落盘) > config 里的 key
        if name != "local_ollama":
            env_key = os.environ.get("DEEPSEEK_API_KEY") or _read_env_key()
            if env_key:
                m["api_key"] = env_key
        try:
            out = _call_openai(m["base_url"], m.get("model"), m.get("api_key", ""),
                               prompt, temperature, max_tokens)
            if out:
                return out
        except Exception:
            continue
    return "[模型不可用]"


def _read_env_key() -> str:
    """从用户环境(HKCU\Environment\DEEPSEEK_API_KEY)读 key, 避免依赖当前进程 env。"""
    try:
        import subprocess, re
        r = subprocess.run(["reg", "query", r"HKCU\Environment", "/v", "DEEPSEEK_API_KEY"],
                           capture_output=True, text=True)
        m = re.search(r"DEEPSEEK_API_KEY\s+REG_SZ\s+(\S+)", r.stdout)
        return m.group(1) if m else ""
    except Exception:
        return ""


def check_active_model() -> dict:
    """模型使用闭环守卫：校验当前激活模型可用性(边界明确报错, 非'怎么都可以')。
    本地Ollama=离线可用; 云端DeepSeek需api_key否则报错(阻止无key云端使用)。"""
    cfg = _load_config()
    active = cfg.get("active", "local_ollama")
    m = cfg.get("models", {}).get(active, {})
    if not m.get("base_url") or not m.get("model"):
        return {"ok": False, "active": active,
                "error": f"模型配置不完整(缺base_url/model): 请到模型设置配置 '{active}'"}
    if active == "local_ollama":
        return {"ok": True, "active": active, "provider": "local",
                "model": m.get("model"), "note": "本地Ollama(离线可用, 本体建模辅助/问答兜底/摘要)"}
    # 云端
    env_key = os.environ.get("DEEPSEEK_API_KEY") or _read_env_key()
    has_key = bool(m.get("api_key")) or bool(env_key)
    if not has_key:
        return {"ok": False, "active": active, "provider": "cloud",
                "model": m.get("model"),
                "error": f"云端模型 '{active}' 未配置API Key：请设置环境变量 DEEPSEEK_API_KEY，或切换回本地模型"}
    return {"ok": True, "active": active, "provider": "cloud",
            "model": m.get("model"), "note": f"云端 {m.get('model')}(key来自环境变量DEEPSEEK_API_KEY, 需网络)"}


if __name__ == "__main__":
    print(llm_generate("用一句话说明补货决策的含义。", temperature=0.1, max_tokens=50))
