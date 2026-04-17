#!/usr/bin/env python3
"""Cloud.ru ML Inference CLI — manage model runs and call inference endpoints.

Usage:
    python ml_inference.py <command> [options]

Commands:
    catalog         List predefined models from Cloud.ru catalog
    catalog-detail  Show deployment configs for a predefined model
    deploy          Deploy a predefined model (recommended way to create)
    list            List all model runs
    get             Get model run details
    create          Create a custom model run (advanced)
    update          Update a model run
    delete          Delete a model run
    suspend         Suspend a model run
    resume          Resume a model run
    call            Call inference (OpenAI-compatible chat)
    embed           Call embedding endpoint
    rerank          Call rerank endpoint
    ping            Health check a model run
    history         Get model run event history
    quotas          Show project quota usage
    frameworks      List available framework/runtime versions

Environment variables required:
    CP_CONSOLE_KEY_ID   — Cloud.ru service account key ID
    CP_CONSOLE_SECRET   — Cloud.ru service account secret
    PROJECT_ID          — Cloud.ru project UUID
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import json

from commands import COMMANDS


def build_parser():
    parser = argparse.ArgumentParser(
        description="Cloud.ru ML Inference CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = subparsers.add_parser("list", help="List model runs")
    p_list.add_argument("--limit", type=int, help="Max results")
    p_list.add_argument("--offset", type=int, help="Offset for pagination")
    p_list.add_argument("--status", help="Filter by status (e.g. MODEL_RUN_STATUS_RUNNING)")
    p_list.add_argument("--all", action="store_true", help="Show all runs including deleted")

    # get
    p_get = subparsers.add_parser("get", help="Get model run details")
    p_get.add_argument("model_run_id", help="Model run UUID")
    p_get.add_argument("--json", action="store_true", dest="output_json", help="Output raw JSON")

    # create
    p_create = subparsers.add_parser("create", help="Create a model run")
    p_create.add_argument("--name", required=True, help="Model run name")
    p_create.add_argument(
        "--framework",
        required=True,
        choices=["VLLM", "SGLANG", "OLLAMA", "TRANSFORMERS", "DIFFUSERS", "COMFY"],
        help="Framework type",
    )
    p_create.add_argument(
        "--resource",
        choices=["GPU_A100", "GPU_H100", "GPU_V100", "CPU"],
        help="Resource type",
    )
    p_create.add_argument(
        "--task",
        help="Task type (e.g. TEXT_2_TEXT_GENERATION, EMBEDDING, TEXT_2_IMAGE_GENERATION)",
    )
    p_create.add_argument(
        "--source-type",
        choices=["huggingface", "ollama", "registry", "modelscope"],
        default="huggingface",
        help="Model source type",
    )
    p_create.add_argument("--repo", help="Repository path (e.g. org/model)")
    p_create.add_argument("--model-name", help="Model name within source")
    p_create.add_argument("--revision", help="Model revision/tag")
    p_create.add_argument("--gpu-count", type=int, help="Number of GPUs")
    p_create.add_argument("--gpu-memory", type=int, help="GPU memory in GB")
    p_create.add_argument("--runtime-template-id", help="Runtime template ID (auto-detected if omitted)")
    p_create.add_argument("--min-scale", type=int, help="Min scale (default: 1)")
    p_create.add_argument("--max-scale", type=int, help="Max scale (default: 1)")
    p_create.add_argument(
        "--vllm-args",
        type=json.loads,
        help='JSON array of dynamical args, e.g. \'[{"key":"dtype","value":"bfloat16","parameterType":"PARAMETER_TYPE_ARG_KV_QUOTED"}]\'',
    )

    # update
    p_update = subparsers.add_parser("update", help="Update a model run")
    p_update.add_argument("model_run_id", help="Model run UUID")
    p_update.add_argument("--name", help="New name")
    p_update.add_argument("--min-scale", type=int, help="New min scale")
    p_update.add_argument("--max-scale", type=int, help="New max scale")
    p_update.add_argument("--keep-alive-minutes", type=int, help="Keep alive minutes")

    # delete
    p_del = subparsers.add_parser("delete", help="Delete a model run")
    p_del.add_argument("model_run_id", help="Model run UUID")

    # suspend
    p_sus = subparsers.add_parser("suspend", help="Suspend a model run")
    p_sus.add_argument("model_run_id", help="Model run UUID")

    # resume
    p_res = subparsers.add_parser("resume", help="Resume a model run")
    p_res.add_argument("model_run_id", help="Model run UUID")

    # call
    p_call = subparsers.add_parser("call", help="Call model inference (chat)")
    p_call.add_argument("model_run_id", help="Model run UUID")
    p_call.add_argument("--prompt", required=True, help="User message")
    p_call.add_argument("--system", help="System message")
    p_call.add_argument("--model-name", help="Model name for the request")
    p_call.add_argument(
        "--framework", choices=["VLLM", "SGLANG", "OLLAMA"], help="Framework hint"
    )
    p_call.add_argument("--temperature", type=float, default=0.7)
    p_call.add_argument("--top-p", type=float, default=0.9)
    p_call.add_argument("--with-auth", action="store_true", help="Use IAM auth for call")

    # embed
    p_embed = subparsers.add_parser("embed", help="Call embedding endpoint")
    p_embed.add_argument("model_run_id", help="Model run UUID")
    p_embed.add_argument("--texts", nargs="+", required=True, help="Texts to embed")
    p_embed.add_argument("--model-name", help="Model name")
    p_embed.add_argument("--with-auth", action="store_true")

    # rerank
    p_rerank = subparsers.add_parser("rerank", help="Call rerank endpoint")
    p_rerank.add_argument("model_run_id", help="Model run UUID")
    p_rerank.add_argument("--query", required=True, help="Query string")
    p_rerank.add_argument("--documents", nargs="+", required=True, help="Documents")
    p_rerank.add_argument("--model-name", help="Model name")
    p_rerank.add_argument("--with-auth", action="store_true")

    # ping
    p_ping = subparsers.add_parser("ping", help="Health check a model run")
    p_ping.add_argument("model_run_id", help="Model run UUID")
    p_ping.add_argument("--with-auth", action="store_true")

    # history
    p_hist = subparsers.add_parser("history", help="Get model run event history")
    p_hist.add_argument("model_run_id", help="Model run UUID")

    # quotas
    subparsers.add_parser("quotas", help="Show project quota usage")

    # frameworks
    subparsers.add_parser("frameworks", help="List available frameworks/runtimes")

    # catalog
    p_catalog = subparsers.add_parser("catalog", help="List predefined models from Cloud.ru catalog")
    p_catalog.add_argument("--query", help="Search query")
    p_catalog.add_argument("--limit", type=int, help="Max results (default: 100)")
    p_catalog.add_argument("--offset", type=int, help="Offset for pagination")
    p_catalog.add_argument(
        "--sort", default="SORT_TYPE_PRICE_ASC",
        help="Sort order (SORT_TYPE_PRICE_ASC, SORT_TYPE_PRICE_DESC, etc.)",
    )

    # catalog-detail
    p_cat_detail = subparsers.add_parser("catalog-detail", help="Show configs for a predefined model")
    p_cat_detail.add_argument("model_card_id", help="Model card UUID from catalog")

    # deploy
    p_deploy = subparsers.add_parser("deploy", help="Deploy a predefined model (recommended)")
    p_deploy.add_argument("model_card_id", help="Model card UUID from catalog")
    p_deploy.add_argument("--name", help="Custom name (default: model name from catalog)")
    p_deploy.add_argument("--config-index", type=int, help="Config index if multiple available (default: 0)")
    p_deploy.add_argument("--wait", action="store_true", help="Wait for model to reach RUNNING status")
    p_deploy.add_argument("--wait-timeout", type=int, default=600, help="Max seconds to wait (default: 600)")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    COMMANDS[args.command](args)


if __name__ == "__main__":
    main()
