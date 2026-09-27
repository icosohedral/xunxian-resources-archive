# 构建与质量报告

- `inventory.json`：全量文件路径、大小、SHA-256、编码、换行、分隔符、行列分布和完整性检查；
- `build_summary.json`：核心资源数量、确定性构建 ID 和未静默跳过的解析异常；
- 后续报告：重复 ID、名称冲突、孤立引用、缺失目标、推测关系和覆盖率。

报告不得包含本机绝对路径、凭据或整份原始游戏内容。`inventory.json` 可由 `uv run python scripts/inventory.py` 重建，并用 `uv run python scripts/inventory.py --check` 检查资料是否发生变化。
