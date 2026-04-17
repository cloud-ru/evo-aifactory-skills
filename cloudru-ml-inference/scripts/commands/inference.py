"""Inference commands: call, embed, rerank, ping."""

import sys

from helpers import build_client, check_response


def cmd_call(args):
    client, _ = build_client()

    messages = [{"role": "user", "content": args.prompt}]
    if args.system:
        messages.insert(0, {"role": "system", "content": args.system})

    payload = {
        "model": args.model_name or "",
        "messages": messages,
        "temperature": args.temperature,
        "top_p": args.top_p,
    }

    res = client.chat(args.model_run_id, payload, use_auth=args.with_auth)
    check_response(res, "calling model")
    result = res.json()
    choices = result.get("choices", [])
    if choices:
        print(choices[0].get("message", {}).get("content", ""))
    usage = result.get("usage", {})
    print(f"\nTokens: {usage.get('total_tokens', '?')}")


def cmd_embed(args):
    client, _ = build_client()

    payload = {
        "model": args.model_name or "",
        "input": args.texts,
    }

    res = client.embed(args.model_run_id, payload, use_auth=args.with_auth)
    check_response(res, "calling embeddings")
    result = res.json()
    for item in result.get("data", []):
        emb = item.get("embedding", [])
        print(f"[{item.get('index', '?')}] dim={len(emb)} first_3={emb[:3]}")
    usage = result.get("usage", {})
    print(f"\nTokens: {usage.get('total_tokens', '?')}")


def cmd_rerank(args):
    client, _ = build_client()

    payload = {
        "model": args.model_name or "",
        "query": args.query,
        "documents": args.documents,
    }

    res = client.rerank(args.model_run_id, payload, use_auth=args.with_auth)
    check_response(res, "calling rerank")
    for r in res.json().get("results", []):
        doc = r.get("document", {})
        print(f"[{r.get('index', '?')}] score={r.get('relevance_score', 0):.4f} | {doc.get('text', '')[:80]}")


def cmd_ping(args):
    client, _ = build_client()
    res = client.ping(args.model_run_id, use_auth=args.with_auth)
    if res.is_success:
        print(f"Model run {args.model_run_id} is healthy")
    else:
        print(
            f"Model run {args.model_run_id} is NOT healthy "
            f"(HTTP {res.status_code})"
        )
        sys.exit(1)
