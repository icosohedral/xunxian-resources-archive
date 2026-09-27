# 外部数据交换

本目录保存与任务资料库等外部项目之间的轻量、可重建数据契约。不得放入任务数据库、D1 导出、搜索索引或网站缓存。

任务项目输出：

```text
data_contracts/imported/quest_resource_links.json
```

资源项目按 `schemas/quest_resource_links.schema.json` 验证。每条关系以 `(resource_kind, resource_id)` 标识资源，以 `quest_id` 标识任务，并保留任务侧 `source_file` 和 `source_row`。页面只按 `quest_site_base_url + /quests/{quest_id}` 生成外链。

交换顺序按可信度从高到低为：原始 ID、官方映射、明确使用／奖励链、人工核实。名称相似候选不进入正式交换文件。

