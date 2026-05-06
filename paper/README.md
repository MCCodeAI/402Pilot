# 402Pilot — Paper Source

LaTeX source. Output: `main.pdf`.

## Compile locally

```bash
cd paper
latexmk -pdf main.tex
```

If `latexmk` is missing:

```bash
pdflatex main && bibtex main && pdflatex main && pdflatex main
```

## Upload to Overleaf

1. From the repo root:

   ```bash
   zip -r 402pilot-paper.zip paper/ -x 'paper/*.aux' 'paper/*.log' \
        'paper/*.bbl' 'paper/*.blg' 'paper/*.out' 'paper/main.pdf'
   ```

2. In Overleaf: **New Project → Upload Project → choose `402pilot-paper.zip`**.
3. Set **Compiler** to **pdfLaTeX** (Menu → Compiler).
4. Hit **Recompile**.

The skeleton uses a stub `\documentclass{article}` plus `geometry` so it compiles immediately, no venue style file required.

## Switch to a venue template

To match a specific venue's typesetting, swap the preamble in `main.tex`. The body content (`sections/`, `references.bib`, the notation macros) is venue-agnostic.

| Venue | Add | Replace `\usepackage[margin=1in]{geometry}` with |
|---|---|---|
| **NeurIPS 2024** | `neurips_2024.sty` | `\usepackage[final]{neurips_2024}` |
| **ICML 2024**    | `icml2024.sty`, `icml2024.bst`, `fancyhdr.sty` | `\usepackage{icml2024}`, also `\bibliographystyle{icml2024}` |
| **ICLR 2024**    | `iclr2024_conference.sty`, `iclr2024_conference.bst` | `\usepackage{iclr2024_conference}` |
| **AAAI 2026**    | `aaai2026.sty` | `\usepackage{aaai2026}` |

In Overleaf the cleanest path is: **New Project → Templates → NeurIPS** (or ICML / ICLR / AAAI), then copy `paper/sections/`, `paper/references.bib`, and the notation macro block from `paper/main.tex` into the template's `main.tex`.

## Layout

```
paper/
├── main.tex                          ← root
├── references.bib                    ← BibTeX (provisional keys; verify before submission)
├── sections/
│   ├── 00_abstract.tex               ← TODO  (write last)
│   ├── 01_introduction.tex           ← TODO
│   ├── 02_related_work.tex           ← ✅ draft v1
│   ├── 03_problem_formulation.tex    ← TODO
│   ├── 04_layer.tex                  ← TODO
│   ├── 05_method.tex                 ← TODO  (Algorithm 1: see logs/algorithm_box.md)
│   ├── 06_evaluation.tex             ← TODO  (numbers in logs/ablation_4metrics_table.md, logs/significance_table.md)
│   ├── 07_discussion.tex             ← TODO
│   ├── 08_conclusion.tex             ← TODO
│   └── A_appendix_notation.tex       ← TODO  (port logs/notation.md)
└── figures/                          ← placeholder; figures created near terminal
```

## Notation reference

Single source of truth for symbols and naming: `../logs/notation.md`. The LaTeX macros at the top of `main.tex` mirror that file. Keep them in sync.

## Citation keys

Provisional. Confirm exact author / venue / arXiv ID before submission, especially the placeholders flagged with `note = {Verify ...}` in `references.bib`:

- `aamas2026reverseauction` — closest adjacent paper
- `sok2026agentpayments` — agent payments survey
- `mixllm2024`, `qi2023dsts`, `a402` — author / venue placeholders
