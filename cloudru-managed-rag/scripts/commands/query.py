"""Search and RAG query commands."""

import os
import sys

from helpers import build_client, check_response, print_json


def _resolve_search_url(client, args, project_id: str) -> str:
    """Get search URL from args, env, or by resolving from KB metadata."""
    url = getattr(args, "search_url", None)
    if url:
        return url

    url = os.environ.get("MANAGED_RAG_SEARCH_URL", "")
    if url:
        return url

    kb_id = getattr(args, "kb_id", None) or os.environ.get("MANAGED_RAG_KB_ID", "")
    if not kb_id:
        print("Error: --kb-id or MANAGED_RAG_KB_ID or MANAGED_RAG_SEARCH_URL required", file=sys.stderr)
        sys.exit(1)

    url = client.resolve_search_url(kb_id, project_id)
    if not url:
        print(f"Error: could not resolve search URL for KB {kb_id}", file=sys.stderr)
        sys.exit(1)
    return url


def _format_search_results(data: dict) -> dict:
    """Format raw API response into cleaner output."""
    results = data.get("results", [])
    chunks = []
    for i, r in enumerate(results, 1):
        chunk = {
            "index": i,
            "score": r.get("score"),
            "content": r.get("content", ""),
            "id": r.get("id", ""),
        }
        meta = r.get("metadata")
        if meta:
            chunk["metadata"] = meta
        chunks.append(chunk)

    output = {"total_results": len(chunks), "chunks": chunks}
    llm_answer = data.get("llm_answer", "")
    if llm_answer:
        output["llm_answer"] = llm_answer
    reasoning = data.get("reasoning_content", "")
    if reasoning:
        output["reasoning_content"] = reasoning
    return output


def cmd_search(args):
    client, project_id = build_client()
    search_url = _resolve_search_url(client, args, project_id)

    res = client.search(
        search_url=search_url,
        query=args.query,
        num_results=args.limit,
        kb_version=args.kb_version,
        rerank_model=args.rerank_model,
        rerank_results=args.rerank_results,
    )
    check_response(res, "searching")
    output = _format_search_results(res.json())
    print_json(output)


def cmd_ask(args):
    client, project_id = build_client()
    search_url = _resolve_search_url(client, args, project_id)

    res = client.ask(
        search_url=search_url,
        query=args.query,
        num_results=args.limit,
        kb_version=args.kb_version,
        model=args.model,
        system_prompt=args.system_prompt,
        rerank_model=args.rerank_model,
        rerank_results=args.rerank_results,
    )
    check_response(res, "asking")
    output = _format_search_results(res.json())
    print_json(output)
