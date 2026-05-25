"""Small Ollama-compatible HTTP facade for a llama.cpp OpenAI API server.

Run ``python ollama_proxy.py --help`` for startup options.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 11435
DEFAULT_TARGET_BASE_URL = "http://127.0.0.1:8081/v1"
DEFAULT_MODEL = "local-llama"
DEFAULT_TIMEOUT = 600.0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run an Ollama-compatible proxy in front of llama.cpp's OpenAI-compatible API.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--host", default=DEFAULT_HOST, help="host/interface for the proxy to listen on")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="port for the proxy to listen on")
    parser.add_argument("--target-base-url", default=DEFAULT_TARGET_BASE_URL, help="llama.cpp OpenAI base URL")
    parser.add_argument("--target-api-key", default="", help="bearer token for the target llama.cpp server")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="model name reported to Ollama clients")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="target request timeout in seconds")
    return parser


def parse_args() -> argparse.Namespace:
    if _PARSED_ARGS is not None:
        return _PARSED_ARGS
    return build_arg_parser().parse_args()


_PARSED_ARGS = build_arg_parser().parse_args() if __name__ == "__main__" else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage httpx.AsyncClient lifecycle for connection pooling."""
    app.state.http_client = httpx.AsyncClient(timeout=DEFAULT_TIMEOUT)
    yield
    await app.state.http_client.aclose()


app = FastAPI(title="llama.cpp Ollama-compatible proxy", lifespan=lifespan)

SETTINGS: dict[str, Any] = {
    "target_base_url": DEFAULT_TARGET_BASE_URL,
    "target_api_key": "",
    "model": DEFAULT_MODEL,
    "timeout": DEFAULT_TIMEOUT,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def target_url(path: str) -> str:
    base = str(SETTINGS["target_base_url"]).rstrip("/")
    return f"{base}{path}"


def default_model(requested: str | None = None) -> str:
    return str(requested or SETTINGS.get("model") or DEFAULT_MODEL).strip()


def target_headers() -> dict[str, str]:
    api_key = str(SETTINGS.get("target_api_key") or "").strip()
    if not api_key:
        return {}
    return {"Authorization": f"Bearer {api_key}"}


def options_to_openai(payload: dict[str, Any]) -> dict[str, Any]:
    options = payload.get("options") or {}
    if not isinstance(options, dict):
        options = {}

    mapped: dict[str, Any] = {}
    mapping = {
        "temperature": "temperature",
        "top_p": "top_p",
        "top_k": "top_k",
        "repeat_penalty": "repeat_penalty",
        "stop": "stop",
        "seed": "seed",
    }
    for source, target in mapping.items():
        if source in options:
            mapped[target] = options[source]
        elif source in payload:
            mapped[target] = payload[source]

    if "num_predict" in options:
        mapped["max_tokens"] = options["num_predict"]
    elif "max_tokens" in payload:
        mapped["max_tokens"] = payload["max_tokens"]

    return mapped


def json_line(data: dict[str, Any]) -> bytes:
    return (json.dumps(data, ensure_ascii=False) + "\n").encode("utf-8")


def ollama_error(message: str, status_code: int = 500) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status_code)


async def post_target_json(path: str, body: dict[str, Any]) -> dict[str, Any]:
    client = app.state.http_client
    response = await client.post(target_url(path), json=body, headers=target_headers())
    response.raise_for_status()
    return response.json()


@app.get("/")
async def root() -> dict[str, str]:
    return {"status": "ok", "target": SETTINGS["target_base_url"]}


@app.get("/api/version")
async def version() -> dict[str, str]:
    return {"version": "llama.cpp-proxy"}


@app.get("/api/tags")
async def tags() -> dict[str, Any]:
    model = default_model()
    return {
        "models": [
            {
                "name": model,
                "model": model,
                "modified_at": now_iso(),
                "size": 0,
                "digest": "llama.cpp",
                "details": {
                    "parent_model": "",
                    "format": "gguf",
                    "family": "llama.cpp",
                    "families": ["llama.cpp"],
                    "parameter_size": "",
                    "quantization_level": "",
                },
            }
        ]
    }


@app.post("/api/chat")
async def chat(request: Request):
    payload = await request.json()
    stream = bool(payload.get("stream", True))
    messages = payload.get("messages") or []
    body = {
        "model": default_model(payload.get("model")),
        "messages": messages,
        "stream": stream,
        **options_to_openai(payload),
    }

    if stream:
        return StreamingResponse(
            stream_chat(body),
            media_type="application/x-ndjson",
        )

    started = time.perf_counter()
    try:
        data = await post_target_json("/chat/completions", body)
    except httpx.HTTPError as exc:
        return ollama_error(str(exc), 502)

    content = ""
    try:
        content = data["choices"][0]["message"].get("content") or ""
    except Exception:
        content = str(data)
    return {
        "model": body["model"],
        "created_at": now_iso(),
        "message": {"role": "assistant", "content": content},
        "done": True,
        "total_duration": int((time.perf_counter() - started) * 1_000_000_000),
    }


async def stream_chat(body: dict[str, Any]) -> AsyncIterator[bytes]:
    client = app.state.http_client
    try:
        async with client.stream(
            "POST",
            target_url("/chat/completions"),
            json=body,
            headers=target_headers(),
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw:
                    continue
                if raw == "[DONE]":
                    break
                try:
                    data = json.loads(raw)
                    delta = data["choices"][0].get("delta") or {}
                    content = delta.get("content") or ""
                except Exception:
                    content = ""
                if content:
                    yield json_line(
                        {
                            "model": body["model"],
                            "created_at": now_iso(),
                            "message": {"role": "assistant", "content": content},
                            "done": False,
                        }
                    )
    except Exception as exc:
        yield json_line({"error": str(exc), "done": True})
        return
    yield json_line({"model": body["model"], "created_at": now_iso(), "done": True})


@app.post("/api/generate")
async def generate(request: Request):
    payload = await request.json()
    stream = bool(payload.get("stream", True))
    prompt = str(payload.get("prompt") or "")
    body = {
        "model": default_model(payload.get("model")),
        "prompt": prompt,
        "stream": stream,
        **options_to_openai(payload),
    }

    if stream:
        return StreamingResponse(
            stream_completion(body),
            media_type="application/x-ndjson",
        )

    started = time.perf_counter()
    try:
        data = await post_target_json("/completions", body)
    except httpx.HTTPError as exc:
        return ollama_error(str(exc), 502)

    text = ""
    try:
        text = data["choices"][0].get("text") or ""
    except Exception:
        text = str(data)
    return {
        "model": body["model"],
        "created_at": now_iso(),
        "response": text,
        "done": True,
        "total_duration": int((time.perf_counter() - started) * 1_000_000_000),
    }


async def stream_completion(body: dict[str, Any]) -> AsyncIterator[bytes]:
    client = app.state.http_client
    try:
        async with client.stream(
            "POST",
            target_url("/completions"),
            json=body,
            headers=target_headers(),
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw:
                    continue
                if raw == "[DONE]":
                    break
                try:
                    data = json.loads(raw)
                    text = data["choices"][0].get("text") or ""
                except Exception:
                    text = ""
                if text:
                    yield json_line(
                        {
                            "model": body["model"],
                            "created_at": now_iso(),
                            "response": text,
                            "done": False,
                        }
                    )
    except Exception as exc:
        yield json_line({"error": str(exc), "done": True})
        return
    yield json_line({"model": body["model"], "created_at": now_iso(), "done": True})


@app.post("/api/embeddings")
async def embeddings(request: Request):
    payload = await request.json()
    prompt = payload.get("prompt", payload.get("input", ""))
    body = {"model": default_model(payload.get("model")), "input": prompt}
    try:
        data = await post_target_json("/embeddings", body)
    except httpx.HTTPError as exc:
        return ollama_error(str(exc), 502)

    items = data.get("data") or []
    embedding = items[0].get("embedding") if items else []
    return {"embedding": embedding}


@app.post("/api/embed")
async def embed(request: Request):
    payload = await request.json()
    input_value = payload.get("input", payload.get("prompt", ""))
    body = {"model": default_model(payload.get("model")), "input": input_value}
    try:
        data = await post_target_json("/embeddings", body)
    except httpx.HTTPError as exc:
        return ollama_error(str(exc), 502)

    embeddings = [item.get("embedding") for item in data.get("data", [])]
    return {"model": body["model"], "embeddings": embeddings}


def main() -> None:
    args = parse_args()
    SETTINGS["target_base_url"] = args.target_base_url.rstrip("/")
    SETTINGS["target_api_key"] = args.target_api_key
    SETTINGS["model"] = args.model
    SETTINGS["timeout"] = args.timeout
    uvicorn.run(app, host=args.host, port=args.port, log_level="info", access_log=True)


if __name__ == "__main__":
    main()
