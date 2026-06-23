"""Write generated exemplars into ``agent/<domain_pack>/exemplars/<lang>/{scripts,utterances,analysis}``.

生成した手本を ``agent/<domain_pack>/exemplars/<lang>/{scripts,utterances,analysis}`` に書き出す.

Also writes a ``_tokens.json`` manifest per (domain, lang) recording the approximate token
counts for the ③ utterance ↔ ⑤ script match (the per-cell table the paper reports — re-measure
with Gemma's tokenizer before publishing).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

# Config domain key -> on-disk domain-pack directory name.
_DOMAIN_PACK = {"aiwolf": "aiwolf", "hiddenbench": "hidden-bench"}


@dataclass
class TokenRecord:
    """Approximate token counts for one generated triple.

    1 つの生成トリプル (台本/発話例/分析) の近似トークン数.
    """

    index: int
    script_tokens: int
    utterances_tokens: int
    analysis_tokens: int
    utterance_to_script_ratio: float


def exemplar_dir(agent_dir: Path, domain: str, lang: str, kind: str) -> Path:
    """Return ``agent/<domain_pack>/exemplars/<lang>/<kind>``.

    手本スロットのディレクトリパスを返す.

    Args:
        agent_dir: Agent project root.
        domain: ``aiwolf`` | ``hiddenbench``.
        lang: ``en`` | ``jp``.
        kind: ``scripts`` | ``utterances`` | ``analysis``.
    """
    return agent_dir / _DOMAIN_PACK[domain] / "exemplars" / lang / kind


def write_triple(
    agent_dir: Path,
    domain: str,
    lang: str,
    index: int,
    *,
    script_md: str,
    utterances_md: str,
    analysis_md: str,
) -> None:
    """Write the script / utterances / analysis files for one example, paired by ``index``.

    1 例分の 台本 / 発話例 / 分析 ファイルを同じ ``index`` で対にして書き出す.

    Args:
        agent_dir: Agent project root.
        domain: ``aiwolf`` | ``hiddenbench``.
        lang: ``en`` | ``jp``.
        index: 1-based example index (used in the filename).
        script_md: Script body (⑤⑥).
        utterances_md: Utterance few-shot body (③④).
        analysis_md: Analysis body (②④⑥).
    """
    stem = f"{index:02d}"
    # (kind dir, singular filename prefix, body).
    for kind, prefix, body in (
        ("scripts", "script", script_md),
        ("utterances", "utterance", utterances_md),
        ("analysis", "analysis", analysis_md),
    ):
        out_dir = exemplar_dir(agent_dir, domain, lang, kind)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{prefix}_{stem}.md").write_text(body.rstrip() + "\n", encoding="utf-8")


def write_token_manifest(
    agent_dir: Path,
    domain: str,
    lang: str,
    records: list[TokenRecord],
) -> Path:
    """Write the per-(domain, lang) token manifest next to the scripts.

    (domain, lang) ごとのトークン一致マニフェストを scripts ディレクトリ脇に書き出す.

    Returns:
        The path to the written manifest.
    """
    out = exemplar_dir(agent_dir, domain, lang, "scripts").parent / "_tokens.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "note": (
            "Approximate token counts (generator's heuristic). The paper's per-cell table "
            "should be re-measured with the discussion agent's (Gemma's) tokenizer."
        ),
        "domain": domain,
        "lang": lang,
        "records": [asdict(r) for r in records],
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return out
