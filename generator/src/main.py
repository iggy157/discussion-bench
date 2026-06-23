"""Entry point: generate the exemplar slots (scripts / utterances / analysis) via Claude.

エントリポイント: 手本スロット (台本 / 発話例 / 分析) を Claude で生成する.

Pipeline per example (one Claude call for the script, one for the analysis; the utterance
few-shot is sliced — not generated — to keep ③ and ⑤ fair to compare):

    script (⑤)  --Claude-->  scripts/script_NN.md
       |  slice (no LLM)
       v
    utterances (③)  ------>  utterances/utterance_NN.md
       |
    analysis (②)  --Claude-->  analysis/analysis_NN.md   (L2: topic-independent, answers stripped)

Leakage control (L1): HiddenBench scripts are built from tasks beyond the evaluation slice;
werewolf scripts use generation-only seeds disjoint from evaluation seeds.

Run:
    uv run src/main.py                      # uses config/generator.yml
    uv run src/main.py -c config/generator.yml
    uv run src/main.py --dry-run            # render prompts, no API calls / no writes
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

from config import GeneratorConfig, load_config
from leakage import aiwolf_seeds, select_hiddenbench_tasks
from prompts import aiwolf_script_prompt, analysis_prompt, hiddenbench_script_prompt
from provider import Provider, build_provider, script_max_tokens
from slicing import build_utterance_block
from tokens import approx_tokens
from writer import TokenRecord, write_token_manifest, write_triple

logger = logging.getLogger("generator")

# Acceptable ③ utterance ↔ ⑤ script token ratio before warning (approximate match).
_RATIO_MIN = 0.8
_RATIO_MAX = 1.2


def _generate_one(
    config: GeneratorConfig,
    provider: Provider,
    domain: str,
    index: int,
    *,
    script_system: str,
    script_user: str,
) -> TokenRecord:
    """Generate one (script, utterances, analysis) triple and write it to disk.

    1 例分の (台本, 発話例, 分析) を生成してディスクに書き出し, トークン記録を返す.
    """
    logger.info("[%s #%d] generating script ...", domain, index)
    script_md = provider.generate(
        system=script_system,
        user=script_user,
        max_tokens=script_max_tokens(config.max_tokens),
        effort="high",
    )

    # ③ utterance few-shot is sliced from the SAME script (fairness backbone). No LLM call.
    utterances_md = build_utterance_block(script_md, lang=config.lang, seed=index)

    logger.info("[%s #%d] generating analysis ...", domain, index)
    ap = analysis_prompt(config.lang, domain, script_md)
    analysis_md = provider.generate(
        system=ap.system,
        user=ap.user,
        max_tokens=config.max_tokens,
        effort="medium",
    )

    write_triple(
        config.agent_dir,
        domain,
        config.lang,
        index,
        script_md=script_md,
        utterances_md=utterances_md,
        analysis_md=analysis_md,
    )

    s_tok = approx_tokens(script_md)
    u_tok = approx_tokens(utterances_md)
    a_tok = approx_tokens(analysis_md)
    ratio = (u_tok / s_tok) if s_tok else 0.0
    if config.token_match == "approximate" and s_tok and not (_RATIO_MIN <= ratio <= _RATIO_MAX):
        logger.warning(
            "[%s #%d] utterance/script token ratio %.2f outside [0.8, 1.2] "
            "(approximate match; re-check with Gemma's tokenizer)",
            domain,
            index,
            ratio,
        )
    logger.info(
        "[%s #%d] tokens: script=%d utterances=%d analysis=%d (u/s=%.2f)",
        domain,
        index,
        s_tok,
        u_tok,
        a_tok,
        ratio,
    )
    return TokenRecord(
        index=index,
        script_tokens=s_tok,
        utterances_tokens=u_tok,
        analysis_tokens=a_tok,
        utterance_to_script_ratio=round(ratio, 3),
    )


def _run_domain(config: GeneratorConfig, provider: Provider, domain: str) -> None:
    """Generate all examples for one domain.

    1 ドメイン分の全例を生成する.
    """
    count = config.num_scripts.get(domain, 0)
    if count <= 0:
        logger.info("[%s] num_scripts=0, skipping", domain)
        return

    if domain == "aiwolf":
        seeds = aiwolf_seeds(count)
        prompts = [aiwolf_script_prompt(config.lang, seed) for seed in seeds]
    else:  # hiddenbench
        tasks = select_hiddenbench_tasks(
            config.hiddenbench.benchmark,
            config.hiddenbench.eval_task_limit,
            count,
        )
        logger.info(
            "[hiddenbench] building from L1-disjoint task ids: %s",
            [t.id for t in tasks],
        )
        prompts = [
            hiddenbench_script_prompt(
                config.lang,
                task,
                config.hiddenbench.total_rounds,
                config.hiddenbench.num_agents,
            )
            for task in tasks
        ]

    records = [
        _generate_one(
            config,
            provider,
            domain,
            index=i + 1,
            script_system=p.system,
            script_user=p.user,
        )
        for i, p in enumerate(prompts)
    ]
    manifest = write_token_manifest(config.agent_dir, domain, config.lang, records)
    logger.info("[%s] wrote %d examples; token manifest: %s", domain, len(records), manifest)


def _dry_run(config: GeneratorConfig) -> None:
    """Render and print prompts without calling the API or writing files.

    API を呼ばず, 書き込みもせずにプロンプトをレンダリングして表示する (検証用).
    """
    for domain in config.domains:
        if domain == "aiwolf":
            p = aiwolf_script_prompt(config.lang, aiwolf_seeds(1)[0])
        else:
            tasks = select_hiddenbench_tasks(
                config.hiddenbench.benchmark,
                config.hiddenbench.eval_task_limit,
                1,
            )
            p = hiddenbench_script_prompt(
                config.lang,
                tasks[0],
                config.hiddenbench.total_rounds,
                config.hiddenbench.num_agents,
            )
        print(f"\n{'=' * 70}\n[{domain}] SCRIPT SYSTEM\n{'=' * 70}\n{p.system}")
        print(f"\n{'-' * 70}\n[{domain}] SCRIPT USER\n{'-' * 70}\n{p.user}")


def main() -> None:
    """Parse args, load config, and run the generation pipeline.

    引数を解釈し, 設定を読み込み, 生成パイプラインを実行する.
    """
    parser = argparse.ArgumentParser(description="Generate exemplar slots via Claude.")
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=Path("config/generator.yml"),
        help="path to generator.yml (default: config/generator.yml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="render prompts only; no API calls, no file writes",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    config = load_config(args.config)

    # Provider keys live in the project root .env (ANTHROPIC_API_KEY); load it before building.
    load_dotenv(config.config_dir.parent / ".env")

    logger.info(
        "config: provider=%s model=%s lang=%s domains=%s",
        config.provider,
        config.model,
        config.lang,
        config.domains,
    )

    if args.dry_run:
        _dry_run(config)
        return

    provider = build_provider(
        config.provider,
        config.model,
        config.temperature,
        config.api_key_env,
        config.base_url,
    )
    for domain in config.domains:
        _run_domain(config, provider, domain)


if __name__ == "__main__":
    main()
