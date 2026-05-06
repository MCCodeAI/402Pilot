# 402Pilot Interactive Explainer

这是一个独立于原 `viz/` 的可视化实现，用于科普 402Pilot 的决策原理并展示锁定实验结果。

## Scope

- 不修改原有 `docs/` 和 `viz/`。
- 使用零依赖静态 HTML/CSS/JS，直接打开 `index.html` 即可查看。
- 数据口径：
  - S1/S2: `results/scenario_sweep/`
  - S3: `results/scenario_sweep_s3promo_v2/`
  - headline 数字与 `logs/m3f_results.md` 的锁定表保持一致。

## Files

- `index.html`: 页面结构。
- `styles.css`: 现代简约样式和动效。
- `app.js`: 图表、交互、状态渲染。
- `data.js`: 轻量展示数据，由脚本生成。
- `scripts/build-data.mjs`: 从本地结果目录重建 `data.js`。

## Rebuild Data

```bash
node viz-explainer/scripts/build-data.mjs
```

当前数据只导出前端需要的聚合信息和代表性 round 样本，不会把完整实验日志打包进页面。
