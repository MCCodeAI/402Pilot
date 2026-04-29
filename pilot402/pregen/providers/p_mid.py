"""P-mid: GPT-5.4-mini with light retrieval-style prompting."""

from __future__ import annotations

from dataclasses import dataclass

from pilot402.core import ProviderId
from pilot402.pregen.providers.base import BaseProvider, LlmBackend
from pilot402.pregen.providers.prompts import P_MID_PROMPT


@dataclass
class PMidProvider(BaseProvider):
    """Mid tier: capable model, prompt instructs concise factual recall.

    The paper's full design includes BM25 retrieval over a small corpus.
    Surface behavior (instructed recall + citation) is encoded in the
    system prompt; the retrieval pipeline is out of scope for the current
    experiments and noted as such in the paper appendix.
    """


def make_p_mid(backend: LlmBackend, base_price_usdc: float) -> PMidProvider:
    return PMidProvider(
        provider_id=ProviderId.P_MID,
        model_name="gpt-5.4-mini",
        base_price_usdc=base_price_usdc,
        system_prompt=P_MID_PROMPT,
        backend=backend,
    )
