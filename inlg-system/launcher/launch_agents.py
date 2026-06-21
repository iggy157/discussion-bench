"""INLG agent launcher: pick domain/condition/lang, build a config, run the agents.

INLGエージェント・ランチャ: ドメイン/条件/言語を選び, 設定を組み立ててエージェントを起動する.

This is the single seam that makes "one config selects what runs" true. It:
  1. resolves the agent main config for (domain, lang),
  2. merges the mode child config (replicating manyshot's load_config),
  3. overlays the chosen condition's ``scenario`` block (from config/conditions/conditions.yml),
     formatting exemplar paths with {domain}/{lang}, and stamps the ``condition`` label,
  4. overrides web_socket.url / agent.team / agent.num from env,
  5. writes a flat merged YAML and runs ``src/main.py -c <tmp>`` inside the agent project.

Safety: if a non-baseline condition is selected but its exemplar directory is empty, the
launcher logs a warning and falls back to baseline behaviour (scenario disabled) so runs
never break on missing-yet exemplars.

「設定ひとつで実行内容が決まる」を実現する継ぎ目. 非baseline条件で手本が空ならbaselineに退避する.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("inlg.launcher")

VALID_DOMAINS = {"aiwolf", "hiddenbench"}
EXEMPLAR_KINDS = {"scripts", "utterances", "analysis"}


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _resolve_main_config(agent_dir: Path, domain: str, lang: str) -> Path:
    """Resolve the agent main config path for (domain, lang) / メイン設定を解決."""
    cfg_dir = agent_dir / "config"
    if domain == "hiddenbench":
        candidates = [cfg_dir / f"config.main.hiddenbench.{lang}.yml"]
    else:  # aiwolf werewolf
        candidates = [cfg_dir / f"config.main.{lang}.yml", cfg_dir / f"config.main.{lang}.yml.example"]
    for c in candidates:
        if c.is_file():
            return c
    msg = f"main config not found for domain={domain} lang={lang} (looked: {[str(c) for c in candidates]})"
    raise FileNotFoundError(msg)


def _merge_mode(main_config: dict[str, Any], main_path: Path) -> dict[str, Any]:
    """Replicate manyshot load_config: merge mode child onto main / モード子設定をマージ."""
    mode = main_config.get("mode")
    configs = main_config.get("configs")
    if mode is None or configs is None:
        return dict(main_config)
    child_rel = configs.get(mode)
    if not child_rel:
        msg = f"mode '{mode}' has no child config in 'configs'"
        raise ValueError(msg)
    child_path = (main_path.parent / child_rel).resolve()
    child = _load_yaml(child_path)
    merged = {**main_config, **child}
    merged["mode"] = mode
    return merged


def _exemplar_dir_has_files(agent_dir: Path, sample_dir_rel: str) -> bool:
    d = agent_dir / sample_dir_rel
    if not d.is_dir():
        return False
    return any(p.is_file() and p.name != ".gitkeep" for p in d.iterdir())


def _apply_condition(
    merged: dict[str, Any],
    agent_dir: Path,
    conditions_path: Path,
    domain: str,
    lang: str,
    condition: str,
) -> dict[str, Any]:
    """Overlay the chosen condition's scenario block + label / 条件のscenarioを重ねる."""
    registry = _load_yaml(conditions_path).get("conditions", {})
    if condition not in registry:
        msg = f"unknown condition '{condition}'. Known: {sorted(registry)}"
        raise ValueError(msg)
    spec = registry[condition]
    merged["condition"] = spec.get("label", condition)
    scenario = dict(spec.get("scenario") or {})
    # Format exemplar path templates and validate exemplar availability.
    sample_dir = scenario.get("sample_dir")
    if sample_dir:
        sample_dir = sample_dir.format(domain=domain, lang=lang)
        scenario["sample_dir"] = sample_dir
    if scenario.get("enabled") and sample_dir and not _exemplar_dir_has_files(agent_dir, sample_dir):
        logger.warning(
            "condition '%s' needs exemplars in %s but it is empty -> falling back to baseline behaviour",
            condition,
            sample_dir,
        )
        scenario = {"enabled": False}
    # Merge onto any existing scenario defaults (condition wins).
    merged["scenario"] = {**(merged.get("scenario") or {}), **scenario}
    return merged


def build_config(
    *,
    agent_dir: Path,
    domain: str,
    lang: str,
    condition: str,
    server_url: str,
    team: str,
    num: int,
    conditions_path: Path,
) -> dict[str, Any]:
    """Build the flat merged agent config / フラットにマージしたエージェント設定を作る."""
    main_path = _resolve_main_config(agent_dir, domain, lang)
    main_config = _load_yaml(main_path)
    merged = _merge_mode(main_config, main_path)
    merged = _apply_condition(merged, agent_dir, conditions_path, domain, lang, condition)
    merged.setdefault("web_socket", {})
    merged["web_socket"]["url"] = server_url
    merged["web_socket"].setdefault("token", None)
    merged["web_socket"]["auto_reconnect"] = True
    merged.setdefault("agent", {})
    merged["agent"]["team"] = team
    merged["agent"]["num"] = num
    # Ensure domain is explicit for the agent dispatch.
    merged["domain"] = domain
    return merged


def main() -> None:
    """CLI / 環境変数優先のCLI."""
    parser = argparse.ArgumentParser(description="Launch INLG agents for a domain/condition/lang")
    parser.add_argument("--agent-dir", default=os.environ.get("AGENT_DIR", ""), help="manyshot project dir")
    parser.add_argument("--domain", default=os.environ.get("DOMAIN", "hiddenbench"))
    parser.add_argument("--lang", default=os.environ.get("LANG_CODE", "en"))
    parser.add_argument("--condition", default=os.environ.get("CONDITION", "baseline"))
    parser.add_argument("--server-url", default=os.environ.get("SERVER_URL", "ws://127.0.0.1:8090/ws"))
    parser.add_argument("--team", default=os.environ.get("TEAM", "inlg-agent"))
    parser.add_argument("--num", type=int, default=int(os.environ.get("NUM", "4")))
    parser.add_argument("--dry-run", action="store_true", help="print the merged config and exit")
    args = parser.parse_args()

    if args.domain not in VALID_DOMAINS:
        logger.error("invalid domain %s (expected one of %s)", args.domain, VALID_DOMAINS)
        sys.exit(2)
    agent_dir = Path(args.agent_dir).resolve()
    if not (agent_dir / "src" / "main.py").is_file():
        logger.error("agent-dir %s does not look like the manyshot project (no src/main.py)", agent_dir)
        sys.exit(2)
    conditions_path = agent_dir / "config" / "conditions" / "conditions.yml"

    merged = build_config(
        agent_dir=agent_dir,
        domain=args.domain,
        lang=args.lang,
        condition=args.condition,
        server_url=args.server_url,
        team=args.team,
        num=args.num,
        conditions_path=conditions_path,
    )
    logger.info(
        "launching %d %s agent(s) | domain=%s lang=%s condition=%s -> %s",
        args.num,
        merged.get("condition"),
        args.domain,
        args.lang,
        merged.get("condition"),
        args.server_url,
    )

    tmp = Path(tempfile.gettempdir()) / f"inlg_agent_{args.domain}_{args.lang}_{args.condition}.yml"
    with tmp.open("w", encoding="utf-8") as f:
        yaml.safe_dump(merged, f, allow_unicode=True, sort_keys=False)
    logger.info("merged config written to %s", tmp)

    if args.dry_run:
        print(tmp.read_text(encoding="utf-8"))
        return

    cmd = [sys.executable, "src/main.py", "-c", str(tmp)]
    logger.info("exec: %s (cwd=%s)", " ".join(cmd), agent_dir)
    subprocess.run(cmd, cwd=str(agent_dir), check=True)  # noqa: S603


if __name__ == "__main__":
    main()
