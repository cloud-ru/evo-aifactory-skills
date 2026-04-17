#!/usr/bin/env python3
"""Cloud.ru Managed RAG CLI.

Manage knowledge bases and query them via semantic search or RAG pipeline.

Requires environment variables:
  CP_CONSOLE_KEY_ID    IAM access key ID
  CP_CONSOLE_SECRET    IAM access key secret
  PROJECT_ID           Cloud.ru project ID

Optional:
  MANAGED_RAG_KB_ID       Default knowledge base ID
  MANAGED_RAG_SEARCH_URL  Default search API URL
  CLOUDRU_ENV_FILE        Path to .env file

Commands:
  Knowledge Base Management:
    list              List all knowledge bases in the project
    get               Get knowledge base details
    versions          List KB versions
    version-detail    Get version details
    delete            Delete a knowledge base
    reindex           Reindex a KB version

  Search & RAG:
    search            Semantic search — returns relevant chunks
    ask               Full RAG pipeline — search + LLM answer
"""

import argparse
import os
import sys

from commands import COMMANDS


def build_parser():
    parser = argparse.ArgumentParser(
        prog="managed_rag",
        description="Cloud.ru Managed RAG CLI",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- list ---
    sub.add_parser("list", help="List knowledge bases")

    # --- get ---
    p = sub.add_parser("get", help="Get KB details")
    p.add_argument("--kb-id", help="KB ID (default: MANAGED_RAG_KB_ID env)")

    # --- versions ---
    p = sub.add_parser("versions", help="List KB versions")
    p.add_argument("--kb-id", help="KB ID (default: MANAGED_RAG_KB_ID env)")

    # --- version-detail ---
    p = sub.add_parser("version-detail", help="Get version details")
    p.add_argument("--version-id", required=True, help="Version ID")
    p.add_argument("--kb-id", help="KB ID (required by API)")

    # --- delete ---
    p = sub.add_parser("delete", help="Delete a knowledge base")
    p.add_argument("--kb-id", help="KB ID (default: MANAGED_RAG_KB_ID env)")

    # --- reindex ---
    p = sub.add_parser("reindex", help="Reindex a KB version")
    p.add_argument("--version-id", required=True, help="Version ID")
    p.add_argument("--kb-id", help="KB ID (default: MANAGED_RAG_KB_ID env)")

    # --- search ---
    p = sub.add_parser("search", help="Semantic search")
    p.add_argument("--query", required=True, help="Search query")
    p.add_argument("--limit", type=int, default=5, help="Number of results (default: 5)")
    p.add_argument("--kb-id", help="KB ID (default: MANAGED_RAG_KB_ID env)")
    p.add_argument("--search-url", help="Search API URL (default: MANAGED_RAG_SEARCH_URL env or auto-resolve)")
    p.add_argument("--kb-version", default="latest", help="KB version (default: latest)")
    p.add_argument("--rerank-model", help="Reranking model name")
    p.add_argument("--rerank-results", type=int, default=0, help="Number of reranked results")

    # --- ask ---
    p = sub.add_parser("ask", help="Search + LLM answer (full RAG)")
    p.add_argument("--query", required=True, help="Question")
    p.add_argument("--limit", type=int, default=3, help="Number of chunks (default: 3)")
    p.add_argument("--kb-id", help="KB ID (default: MANAGED_RAG_KB_ID env)")
    p.add_argument("--search-url", help="Search API URL (default: auto-resolve)")
    p.add_argument("--kb-version", default="latest", help="KB version (default: latest)")
    p.add_argument("--model", default="t-tech/T-lite-it-1.0", help="LLM model for generation")
    p.add_argument("--system-prompt", help="System prompt for LLM")
    p.add_argument("--rerank-model", help="Reranking model name")
    p.add_argument("--rerank-results", type=int, default=0, help="Number of reranked results")

    # --- setup ---
    p = sub.add_parser("setup", help="Full RAG infra setup (requires CP_CONSOLE_KEY_ID/SECRET/PROJECT_ID env)")
    p.add_argument("--docs-path", required=True, help="Path to documents folder")
    p.add_argument("--kb-name", required=True, help="Knowledge base name")
    p.add_argument("--bucket-name", required=True, help="S3 bucket name")
    p.add_argument("--project-id", default=os.environ.get("PROJECT_ID"), help="Project ID (default: PROJECT_ID env)")
    p.add_argument("--file-extensions", default="txt,pdf", help="File extensions to upload")
    p.add_argument("--output-env", help="Path to save .env file")
    p.add_argument("--dry-run", action="store_true", help="Preview without API calls")

    # --- setup-step ---
    p = sub.add_parser("setup-step", help="Run single setup step")
    p.add_argument("--step", required=True, choices=[
        "get-iam-token", "get-tenant-id", "ensure-bucket", "upload-docs",
        "create-kb", "wait-active", "save-env",
    ])
    p.add_argument("--project-id", default=os.environ.get("PROJECT_ID"), help="Project ID (default: PROJECT_ID env)")
    p.add_argument("--docs-path", help="Path to documents folder")
    p.add_argument("--kb-name", help="Knowledge base name")
    p.add_argument("--bucket-name", help="S3 bucket name")
    p.add_argument("--file-extensions", default="txt,pdf", help="File extensions to upload")
    p.add_argument("--output-env", help="Path to save .env file")
    p.add_argument("--dry-run", action="store_true", help="Preview without API calls")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    handler = COMMANDS.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)
    handler(args)


if __name__ == "__main__":
    main()
