# 402Pilot — Paper Source (NeurIPS 2026)

LaTeX source. Output: `neurips_2026.pdf`.

## File map

```
paper/
├── neurips_2026.tex             ← root (compile this)
├── neurips_2026.sty             ← NeurIPS 2026 official style file
├── checklist.tex                ← NeurIPS reproducibility checklist (mandatory)
├── references.bib               ← BibTeX (provisional keys; verify before submission)
├── sections/
│   ├── 00_abstract.tex          ← TODO
│   ├── 01_introduction.tex      ← TODO
│   ├── 02_related_work.tex      ← ✅ draft v1
│   ├── 03_problem_formulation.tex
│   ├── 04_layer.tex
│   ├── 05_method.tex            ← Algorithm 1 spec in logs/algorithm_box.md
│   ├── 06_evaluation.tex        ← numbers in logs/ablation_4metrics_table.md, logs/significance_table.md
│   ├── 07_discussion.tex
│   ├── 08_conclusion.tex
│   └── A_appendix_notation.tex  ← port logs/notation.md
└── figures/                     ← placeholder; figures generated near terminal
```

## Compile locally

```bash
cd paper
latexmk -pdf neurips_2026.tex
```

If `latexmk` is missing:

```bash
pdflatex neurips_2026 && bibtex neurips_2026 && pdflatex neurips_2026 && pdflatex neurips_2026
```

## Overleaf

This `paper/` directory IS the Overleaf project root (via `git subtree`). Sync via:

```bash
# From repo root, push paper/ to Overleaf:
git subtree push --prefix=paper https://git@git.overleaf.com/<PROJECT_ID> master

# Or pull Overleaf changes back into local paper/:
git subtree pull --prefix=paper https://git@git.overleaf.com/<PROJECT_ID> master --squash
```

Username is `git` (already in URL); password is your Overleaf **Git Authentication Token**.

In Overleaf settings: **Compiler = pdfLaTeX**, **Main document = neurips_2026.tex**.

## Submission track switching

Default track (`\usepackage{neurips_2026}`) = Main Track, anonymized for double-blind review. Other tracks set the option explicitly:

| Track | Option |
|---|---|
| Main Track | `\usepackage{neurips_2026}` (default) or `\usepackage[main]{neurips_2026}` |
| Position Paper | `\usepackage[position]{neurips_2026}` |
| Evaluations & Datasets | `\usepackage[eandd]{neurips_2026}` |
| Creative AI | `\usepackage[creativeai]{neurips_2026}` |
| Workshop (single-blind) | `\usepackage[sglblindworkshop]{neurips_2026}` |
| Workshop (double-blind) | `\usepackage[dblblindworkshop]{neurips_2026}` |
| arXiv preprint | `\usepackage[preprint]{neurips_2026}` |
| Camera-ready | append `, final` to the option, e.g. `\usepackage[main, final]{neurips_2026}` |

For workshops, also set `\workshoptitle{...}` after `\title{...}`.

## Notation reference

Single source of truth: `../logs/notation.md`. The LaTeX macros in `neurips_2026.tex` mirror its §10. Keep them in sync.

## Citation keys

Provisional. Confirm exact author / venue / arXiv ID before submission, especially:

- `aamas2026reverseauction` — closest adjacent paper
- `sok2026agentpayments`, `mixllm2024`, `qi2023dsts`, `a402` — placeholders flagged in `references.bib`.
