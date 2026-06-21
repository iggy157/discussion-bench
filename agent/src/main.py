"""Script to launch agents according to configuration.

設定に応じたエージェントを起動するスクリプト.
"""

from __future__ import annotations

import argparse
import logging
import multiprocessing
from pathlib import Path
from typing import Any

import yaml

from starter import connect

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
console_handler.setFormatter(formatter)


def load_config(config_path: Path) -> dict[str, Any]:
    """Load main config and merge the mode-specific child config.

    メインconfigを読み込み, モードに応じた子configをマージして返す.

    The main config must define `mode` (multi_turn / single_turn) and `configs`
    which maps each mode to a child config path (relative to the main config).
    The child config is merged on top of the main config: on key conflict,
    the child config wins.

    Legacy flat configs (without `mode` / `configs`) are still accepted and
    returned as-is.

    Args:
        config_path (Path): Path to the main configuration file / メイン設定ファイルのパス

    Returns:
        dict[str, Any]: Merged configuration / マージ済みの設定
    """
    with Path.open(config_path) as f:
        main_config = yaml.safe_load(f)

    mode = main_config.get("mode")
    configs = main_config.get("configs")
    if mode is None or configs is None:
        return _apply_file_prompts(main_config)

    child_rel = configs.get(mode)
    if not child_rel:
        msg = f"モード '{mode}' に対応する子configファイルが configs で定義されていません"
        raise ValueError(msg)

    child_path = (config_path.parent / child_rel).resolve()
    with Path.open(child_path) as f:
        child_config = yaml.safe_load(f) or {}

    merged: dict[str, Any] = {**main_config, **child_config}
    merged["mode"] = mode
    return _apply_file_prompts(merged)


# Prompts are managed as per-system files under agent/<pack>/prompts/<lang>/<mode>/*.jinja.
# プロンプトは agent/<pack>/prompts/<lang>/<mode>/*.jinja にシステム別ファイルとして管理する.
_AGENT_ROOT = Path(__file__).resolve().parent.parent  # inlg/agent


def _load_domain_prompts(domain: str, lang: str, mode: str) -> dict[str, str]:
    """Load per-system prompt files into a {request_key: template} dict / プロンプトファイルを読む.

    Files live in agent/<pack>/prompts/<lang>/<mode>/*.jinja, where pack = aiwolf |
    hidden-bench. Returns {} if the directory is absent (then inline config is used).
    """
    pack = "hidden-bench" if str(domain).lower() == "hiddenbench" else "aiwolf"
    prompt_dir = _AGENT_ROOT / pack / "prompts" / str(lang) / str(mode)
    out: dict[str, str] = {}
    if prompt_dir.is_dir():
        for p in sorted(prompt_dir.glob("*.jinja")):
            out[p.stem] = p.read_text(encoding="utf-8")
    return out


def _apply_file_prompts(config: dict[str, Any]) -> dict[str, Any]:
    """Overlay per-system prompt files onto config['prompt'] / ファイルプロンプトを重ねる.

    File prompts override inline config entries (keeping non-template flags like
    ``narration_split``). If no files exist, the inline config is kept unchanged.
    ファイルが優先。narration_split 等の非テンプレ設定は config 側を維持。
    """
    file_prompts = _load_domain_prompts(
        config.get("domain", "aiwolf"),
        config.get("lang", "jp"),
        config.get("mode", "multi_turn"),
    )
    if file_prompts:
        config["prompt"] = {**(config.get("prompt") or {}), **file_prompts}
    return config


def execute(config_path: Path) -> None:
    """Execute based on the configuration file.

    設定ファイルをもとに実行する.

    Args:
        config_path (Path): Path to the configuration file / 設定ファイルのパス
    """
    config = load_config(config_path)
    logger.info("設定ファイルを読み込みました (mode=%s)", config.get("mode", "legacy"))

    agent_num = int(config["agent"]["num"])
    threads: list[multiprocessing.Process] = []
    for i in range(agent_num):
        thread = multiprocessing.Process(
            target=connect,
            args=(config, i + 1),
        )
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        nargs="+",
        default=["./config/config.main.jp.yml"],
        help="メイン設定ファイルのパス (複数指定可). 既定: ./config/config.main.jp.yml (英語プロンプトは ./config/config.main.en.yml)",
    )
    args = parser.parse_args()

    paths: list[Path] = []
    for config_path in args.config:
        glob_path = Path(config_path)
        paths.extend([path for path in Path.glob(glob_path.parent, glob_path.name) if path.is_file()])

    multiprocessing.set_start_method("spawn")
    threads: list[multiprocessing.Process] = []
    for path in paths:
        thread = multiprocessing.Process(
            target=execute,
            args=(Path(path),),
        )
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()
