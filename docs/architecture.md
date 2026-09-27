# 项目架构

数据流保持单向：

```text
original_data/（只读）
  → parsers（保留原始行与来源位置）
  → builders（规范实体与本地数据库）
  → relations（直接、映射、人工与推测关系分层）
  → web（本地查询数据库）
  → Cloudflare 构建器（压缩的网页查询数据）
  → D1 + Python Worker + Static Assets
  → https://xunxian.wiki/
```

任务资料库不属于这条数据流。它独立生成轻量 `quest_resource_links.json`，本项目验证后按任务 ID 建立外链。

## 边界

- `original_data/`：本地权威输入，Git 忽略；
- `src/`：解析、构建、关系和网站代码；
- `schemas/`：SQLite、JSON Schema 和字段字典；
- `config/`：来源路由、编号空间与展示配置；
- `curated/`：人工核实的补充与纠错；
- `data_contracts/`：外部项目轻量交换约定；
- `outputs/`：可重建数据库和索引，Git 忽略；
- `reports/`：可重建清单和质量摘要；
- `public/`：项目自有、可公开的静态文件。
- `apps/resource_viewer_cloudflare/`：线上 Worker、D1 构建脚本与发布配置。

线上资源数据库只包含页面查询所需的规范化索引和压缩详情，不上传
`original_data/`、完整本地构建库或任务数据库。来访统计使用独立 D1，
避免与只读资源数据混写。

坐骑技能不是新的资源编号空间，而是骑乘配置的从属记录。
`ride_skill_link` 原样保留 `ride_list` 的六个技能槽，`ride_skill`
优先使用专用坐骑技能表确定名称和内部备注，并以 NPC 技能表补足玩家
可读的完整效果说明与图标键。两处来源分别保存；未命中的技能编号仍
保留在链接表和质量报告中，页面明确标记为未解析。

NPC／Boss 战斗属性、状态三元组和状态组编号空间的已确认规则见
[`NPC_BATTLE_ATTRIBUTE_PARSING.md`](NPC_BATTLE_ATTRIBUTE_PARSING.md)。解析
`cha_list` 附加状态时必须先连接 `state_group`，再使用组内状态数据 ID连接
`state_data`；禁止绕过状态组按相同数字直接匹配。

当前已经整理的 MB 文件含义、字段状态和跨表关系总览见
[`MB_FILE_AND_RELATION_REFERENCE.md`](MB_FILE_AND_RELATION_REFERENCE.md)。该文档
是统一入口；具体道具类型、NPC 战斗字段和宠物分类仍以各专项文档为准。

## 可追溯性

原始层按实际物理行保存 `source_file`、`source_row`、`raw_value`、`raw_values_json` 和确定性 `build_id`。业务实体以 `(resource_kind, resource_id)` 为主键，并指向选中的来源版本；同编号空间内的重复来源记录不会被丢弃。

## 关系可信度

`source`、`mapped`、`curated` 和 `inferred` 分开保存。多跳关系保留完整路径；低置信度推测只进入待核实报告，不默认展示为正式事实。
