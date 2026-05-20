# Reference Audit

Audit date: 2026-05-20

Scope: checked every cited BibTeX entry in `paper/references.bib` against the
manuscript citation context in `paper/sections/*.tex`. The bibliography contains
27 real cited entries, with no unused bibliography entries and no missing cited
keys. The ACM template comments in `paper/main.tex` contain `\citestyle` examples
that can confuse naive citation extraction; they are not manuscript citations.

## Changes Made

- Corrected `chen2021humaneval`: the paper/GitHub citation lists `Brooke Chan`,
  not `Jan Chan`; changed the entry from `@inproceedings` with an arXiv
  `booktitle` to `@article` with an arXiv `journal` field.
- Updated access dates for x402 V2, AP2, A2A x402, and the Patra et al. arXiv
  caveat to 2026-05-19.
- Added the official JAIR URL to `trovo2020sliding`.
- Softened the proof appendix's misspecified-Gaussian-TS language: the paper now
  claims the cited regret results only for the well-specified reduction, and no
  longer asserts an unverified misspecified-TS regret theorem.
- Added `agrawal2013contextualts` alongside `russo2014learning` where the method
  text names contextual Thompson sampling.
- Added dataset citations in the benchmark paragraph for HumanEval, HotpotQA,
  TriviaQA, and OpenAssistant; removed the unused `gebru2021datasheets` entry.

## Entry-by-Entry Audit

| Key | Primary/official source checked | Result |
| --- | --- | --- |
| `coinbase2025x402v2` | https://www.x402.org/writing/x402-v2-launch | Real source. Title, authors, date, and claims about V2 discovery, dynamic routing/pricing, extensibility, wallet/session access, and metadata are supported. |
| `google2025ap2` | https://cloud.google.com/blog/products/ai-machine-learning/announcing-agents-to-payments-ap2-protocol | Real Google Cloud Blog source. Title, authors, date, and payment-agnostic AP2 authorization framing are supported. |
| `a2ax402` | https://github.com/google-agentic-commerce/a2a-x402 | Real GitHub repository. README supports A2A cryptocurrency/on-chain payment flow; repository page shows v0.1.0 release. |
| `a402` | https://arxiv.org/abs/2603.01179 | Real arXiv paper. Title, authors, arXiv DOI, and "binding payments to service execution through Atomic Service Channels" are supported. |
| `sok2026agentpayments` | https://arxiv.org/abs/2604.03733 | Real arXiv paper. Title, authors, DOI string, and four-stage lifecycle of discovery, authorization, execution, and accounting are supported. Caveat: arXiv-only as checked. |
| `xia2015bts` | https://www.ijcai.org/Proceedings/15/Papers/556.pdf | Real IJCAI 2015 paper. Budgeted MAB, reward/cost posterior sampling, ratio selection, and finite-budget framing are supported. |
| `qi2023dsts` | https://arxiv.org/abs/2305.10718 | Real arXiv paper. DS-TS with Gaussian priors and discounting for non-stationary bandits is supported. |
| `agrawal2013contextualts` | https://proceedings.mlr.press/v28/agrawal13.html | Real PMLR/ICML 2013 paper. Title, authors, PMLR volume/number/pages, and contextual Thompson sampling with linear payoffs are supported. |
| `li2010linucb` | https://arxiv.org/abs/1003.0146 and https://doi.org/10.1145/1772690.1772758 | Real WWW 2010 paper. Title, authors, ACM DOI, and contextual-bandit news recommendation framing are supported. |
| `badanidiyuru2018bandits` | https://arxiv.org/abs/1305.2545 and https://doi.org/10.1145/3164539 | Real JACM paper. Bandits with knapsacks and budget/resource constraints are supported. |
| `agrawal2016linearcbwk` | https://proceedings.neurips.cc/paper/2016/hash/f3144cefe89a60d6a1afaf7859c5076b-Abstract.html | Real NeurIPS 2016 paper. Linear contextual bandits with resource consumption/knapsack constraints are supported. |
| `russac2019weighted` | https://papers.nips.cc/paper_files/paper/2019/hash/263fc48aae39f219b4c71d9d4bb4aed2-Abstract.html | Real NeurIPS 2019 paper. Discounted/weighted linear regression for non-stationary linear bandits is supported. |
| `chen2023frugalgpt` | https://arxiv.org/abs/2305.05176 | Real arXiv paper. FrugalGPT cascade, cost reduction, and quality/cost motivation are supported. |
| `ong2024routellm` | https://arxiv.org/abs/2406.18665 | Real arXiv paper. RouteLLM title, authors, DOI, and preference-data routing for cost/quality tradeoff are supported. |
| `ding2024hybridllm` | https://openreview.net/forum?id=02f3mUtqnM | Real ICLR 2024 OpenReview entry. Query routing between small/large models with quality/cost tradeoff is supported. |
| `mixllm2024` | https://aclanthology.org/2025.naacl-long.545/ | Real ACL Anthology entry. Metadata, DOI, pages, and dynamic routing with quality/cost/latency tradeoffs are supported. |
| `madaan2024automix` | https://proceedings.neurips.cc/paper_files/paper/2024/hash/ecda225cb187b40ea8edc1f46b03ffda-Abstract-Conference.html | Real NeurIPS 2024 paper. Metadata, DOI, and routing queries to larger LMs via self-verification/POMDP router are supported. |
| `llmbandit2025` | https://arxiv.org/abs/2502.02743 | Real arXiv paper. One-author metadata and preference-conditioned dynamic LLM routing as a bandit problem are supported. Caveat: arXiv-only as checked. |
| `russo2014learning` | https://pubsonline.informs.org/doi/10.1287/moor.2014.0650 | Real Mathematics of Operations Research article. Posterior sampling and broad Bayesian regret-bound framing are supported. |
| `garivier2011discounted` | https://link.springer.com/chapter/10.1007/978-3-642-24412-4_16 | Real ALT 2011/Springer chapter. Discounted UCB and sliding-window UCB for switching bandits are supported. |
| `trovo2020sliding` | https://www.jair.org/index.php/jair/article/view/11407 | Real JAIR article. Title, four authors, publication date, DOI, volume, and non-stationary sliding-window TS claims are supported. |
| `lattimore2020bandit` | https://www.cambridge.org/core/books/bandit-algorithms/8E39FD004E6CE036680F90DD0C6F09FC | Real Cambridge University Press book. Metadata and DOI are supported. Used only for broad bandit/Thompson-sampling background after edits. |
| `chen2021humaneval` | https://arxiv.org/abs/2107.03374 and https://github.com/openai/human-eval | Real arXiv paper and OpenAI repository. Metadata corrected to Brooke Chan; HumanEval dataset/repository and MIT license are supported. |
| `yang2018hotpotqa` | https://aclanthology.org/D18-1259/ and https://github.com/hotpotqa/hotpot | Real ACL/EMNLP paper. Title, authors, pages, DOI, and multi-hop QA dataset framing are supported. Dataset license CC BY-SA 4.0 is supported by official GitHub README. |
| `joshi2017triviaqa` | https://aclanthology.org/P17-1147/ and https://huggingface.co/datasets/zechen-nlp/triviaqa/blob/main/README.md | Real ACL paper. Title, authors, pages, DOI, and TriviaQA dataset framing are supported. Apache-2.0 license is supported by dataset metadata source checked. |
| `kopf2023openassistant` | https://proceedings.neurips.cc/paper_files/paper/2023/hash/949f0f8f32267d297c2d4e3ee10a2e7e-Abstract-Datasets_and_Benchmarks.html | Real NeurIPS Datasets and Benchmarks paper. Metadata and OpenAssistant conversation dataset framing are supported. |
| `patra2026reverseauction` | https://arxiv.org/abs/2602.14476 | Real arXiv paper. Title, authors, DOI, and reverse-auction/contextual-MAB framing are supported. Caveat: no peer-reviewed venue found as of this audit. |

## Remaining Caveats

- Several cited payment/agent-commerce sources are intentionally current web,
  GitHub, or arXiv sources rather than archival conference papers:
  `coinbase2025x402v2`, `google2025ap2`, `a2ax402`, `a402`,
  `sok2026agentpayments`, and `patra2026reverseauction`.
- `sok2026agentpayments`, `llmbandit2025`, and `patra2026reverseauction` were
  treated as arXiv-only sources during this audit; the manuscript should not
  imply peer-reviewed publication for them.
- The proof appendix now explicitly avoids claiming a formal regret theorem for
  the exact misspecified proxy-variance hyperparameters used in the benchmark.
