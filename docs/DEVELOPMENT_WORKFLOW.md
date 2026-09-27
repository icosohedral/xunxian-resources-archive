# 寻仙道具、宠物与称号资料库开发流程

本文档用于规划一个独立的《寻仙》道具、宠物与称号资料整理及展示项目。新项目以本地 `original_data/` 为只读资料源，同时与现有的寻仙任务资料库建立稳定链接。

## 一、项目目标

首期整理三类资源：

- 道具：名称、类型、说明、使用方式、获取线索、关联配方、商店、任务和其他资源。
- 宠物与骑宠：名称、种类、外形、属性、技能、骑乘配置、获取道具和相关图鉴。
- 称号：名称、分组、说明、属性效果、获得条件和相关任务。

页面中的资料应能互相跳转。例如：

- 道具页可以查看哪些任务会奖励、要求或收集该道具；
- 宠物页可以跳转到对应的获取道具、技能、骑乘配置和风物志；
- 称号页可以跳转到关联任务或授予称号的道具；
- 任务链接统一跳到现有任务站，而不在新项目中复制一份任务页面。

## 二、新项目中应该放入什么

除了只读的 `original_data/`，建议建立以下内容。

```text
new-resource-archive/
├── original_data/                 # 本地原始资料，只读，不提交 Git
├── src/                           # 解析、规范化、关联和导出代码
│   ├── parsers/
│   ├── builders/
│   ├── relations/
│   └── web/
├── scripts/                       # 清点、构建、校验、部署等命令入口
├── schemas/                       # 数据库结构、JSON Schema、字段说明
├── config/                        # 来源路由、字段映射、展示配置
├── curated/                       # 经人工核实的补充关系与纠错
├── data_contracts/                # 与任务站等外部项目交换数据的约定
├── tests/                         # 解析、关系、接口和页面测试
├── reports/                       # 构建时生成的覆盖率与异常报告
├── public/                        # 网站自有静态文件
├── outputs/                       # 数据库、SQL、索引等构建产物，不提交
├── docs/
├── README.md
├── .gitignore
├── .env.example
├── pyproject.toml                 # 或所选语言的依赖清单
└── uv.lock                        # 锁定依赖版本；采用其他工具时保留对应锁文件
```

### 必须纳入版本控制的文件

- 所有解析、规范化、关联、校验和网站代码；
- 数据库 Schema、字段字典和数据交换 Schema；
- 人工确认的纠错、别名和资源关系；
- 测试及少量不含游戏原始内容的合成测试样本；
- 构建与部署脚本；
- `README.md`、本流程文档、项目决策记录；
- `.gitignore`、`.env.example`、依赖清单和锁文件；
- 自己创作或明确可公开的网页图标、样式和界面资源。

### 不应纳入版本控制的文件

- `original_data/` 及其压缩包或备份；
- 由原始资料生成的完整 SQLite、D1 SQL、搜索索引和缓存；
- 未确认可以公开的游戏图片、模型、音频及批量转换结果；
- `.env`、Cloudflare 凭据、令牌和本地部署状态；
- 虚拟环境、依赖目录、测试缓存和日志；
- 本机绝对路径、个人访问记录和临时分析文件。

不要为了方便而提交一份现有任务数据库。数据库容易过期，也会使两个项目各自维护一份任务事实。应交换可重建的小型关系文件，或者通过稳定接口访问任务站。

## 三、建议从现有任务项目复用的内容

以下内容适合复制后按新项目调整：

- `src/questdb/parser.py` 中对制表符文本、编码和来源行号的处理方式；
- `src/questdb/raw_store.py` 的原始值留存思路；
- `docs/quest_info_schema.json` 及 `docs/database_schema.md` 中已经确认的任务字段含义；
- 测试、质量报告和可重复构建的组织方式；
- `.gitignore` 中关于 `original_data/`、数据库、虚拟环境、密钥和 Cloudflare 本地状态的规则。

下列内容不应直接复制为新项目的数据源：

- `outputs/**/quest.db`；
- `apps/quest_viewer_cloudflare/data/quest_web*`；
- `reports/` 中某一次构建产生的统计数字；
- Cloudflare 生成模块和部署状态。

现有任务站的稳定访问地址为：

```text
https://quests.xunxian.wiki/quests/{quest_id}
```

新站只需保存 `quest_id`、任务名称和关系类型，链接在展示时按上述格式生成。

## 四、数据建模的硬性规则

### 1. 保留来源证据

每条规范化记录和关系至少保存：

- `source_file`
- `source_row`
- `raw_value` 或 `raw_values_json`
- `build_id`

界面可以隐藏这些技术字段，但数据库中不能丢失。发现误判时，必须能够回到原文件的具体一行。

### 2. 不同编号空间不得混合

至少使用 `(resource_kind, resource_id)` 作为资源身份，不得只使用数字 ID。

例如：

- `item:15659`：普通道具；
- `quest_item:15659`：任务逻辑道具；
- `pet:1515`：宠物；
- `title:1515`：称号。

这些编号即使相同，也不能自动视为同一资源。

任务系统中尤其要注意：

- 任务奖励的对象类型 2 通常连接普通道具 `mb/item/item_list*.txt`；
- 任务条件和任务目标的对象类型 2 连接任务道具 `mb/quest/quest_item.txt`；
- 普通道具和任务道具只有存在明确映射时才能合并展示。

### 3. 原始资料与人工整理分层

关系应标记来源：

- `source`：原始文件明确记录；
- `mapped`：通过明确映射表连接；
- `curated`：人工核实后补充；
- `inferred`：依据名称、文本或邻近字段推测。

面向访问者时可以使用自然语言展示，但后台不能把推测伪装成原始事实。低置信度关系默认不作为正式链接。

### 4. 删除与覆盖必须可追踪

不要修改 `original_data/`。字段解释变化时，应修改解析器、Schema 或 `curated/` 中的纠错文件，并通过 Git 记录原因。

## 五、首期需要重点解析的来源

这不是最终清单；第一次清点应覆盖 `original_data/` 全部内容，再按实体逐步接入。

### 道具

- `mb/item/item_list.txt`
- `mb/item/item_list2.txt`
- `mb/item/item_list3.txt`
- `mb/item/item_type.txt`
- `mb/item/item_use.txt`
- `mb/item/item_rand.txt`
- `mb/item/item_combin.txt`
- `mb/item/item_derive.txt`
- `mb/item/item_mcht.txt`
- `mb/item/item_pet.txt`
- `mb/item/item_award.txt`
- `mb/item/item_collect*.txt`
- `mb/item/quest_shop_item.txt`
- `mb/quest/quest_item.txt`
- `mb/quest/quest_item_ex.txt`
- `mb/quest/quest_item_mapping.txt`

### 宠物与骑宠

- `mb/pet/pet_list.txt`
- `mb/pet/pet_list_group.txt`
- `mb/pet/pet_text.txt`
- `mb/pet/pet_model.txt`
- `mb/pet/pet_ability.txt`
- `mb/pet/pet_newskill_list.txt`
- `mb/pet/pet_fetter.txt`
- `mb/pet/pet_catch.txt`
- `mb/pet/car_skill.txt`
- `mb/object/ride_list.txt`
- `mb/object/ride_connection.txt`
- `mb/object/cha_list.txt`
- `mb/object/cha_pic.txt`

宠物、骑宠、战斗载具和怪物乘骑可能共用外形或名称，但不是同一实体。必须根据宠物 ID、角色 ID、骑乘配置 ID 和技能槽分别建模。

### 称号

- `mb/etc/title_list.txt`
- `mb/etc/title_group.txt`
- `mb/etc/title_share.txt`
- `mb/etc/itemaddtitle.txt`
- `mb/camp/camp_level_title.txt`
- `mb/compete/compete_title.txt`
- 其他活动或系统目录中的 `*_title.txt`

### 风物志及跨资源关系

- `mb/collection/col_list.txt`
- `mb/collection/col_text.txt`
- `mb/collection/col_reward.txt`
- `mb/collection/col_quest.txt`
- `mb/collection/col_type.txt`

## 六、道具与任务的关联约定

建议在任务项目中生成、在新项目中读取一个小型交换文件：

```text
data_contracts/imported/quest_resource_links.json
```

每条记录建议采用以下结构：

```json
{
  "resource_kind": "item",
  "resource_id": 15659,
  "quest_id": 1234,
  "quest_name": "任务名称",
  "relation_type": "reward",
  "amount": 1,
  "source_file": "mb/quest/quest_info.txt",
  "source_row": 1235,
  "quest_site_path": "/quests/1234"
}
```

`relation_type` 至少支持：

- `reward`：任务奖励普通道具；
- `required`：接取或完成任务前要求持有某资源；
- `objective`：任务目标要求收集或使用任务道具；
- `accept_endpoint`：通过任务逻辑道具触发接取；
- `submit_endpoint`：向任务逻辑道具提交；
- `title_reward`：任务授予称号；
- `pet_reward`：任务直接或经奖励道具授予宠物。

不要只依赖名称进行关联。优先顺序应为：

1. 原始 ID 直接引用；
2. 官方映射表；
3. 使用效果或奖励链的明确 ID；
4. 人工核实关系；
5. 名称相似推测，仅进入待核实报告。

交换文件必须包含格式版本，例如：

```json
{
  "schema_version": 1,
  "generated_at": "2026-07-28T00:00:00Z",
  "quest_site_base_url": "https://quests.xunxian.wiki",
  "links": []
}
```

同时在 `schemas/quest_resource_links.schema.json` 保存对应 JSON Schema，并为导入兼容性编写测试。

## 七、推荐开发阶段

### 阶段 0：建立仓库边界

1. 创建新 Git 仓库。
2. 写入 `.gitignore`，先忽略 `original_data/`、`outputs/`、数据库、密钥和虚拟环境。
3. 再把 `original_data/` 放入仓库目录。
4. 用 `git status --ignored` 确认原始资料不会进入提交。
5. 记录运行环境和依赖锁文件。

验收：

- Git 待提交列表中没有原始游戏文件、数据库或密钥；
- 任意开发者按照 README 可以建立相同环境。

### 阶段 1：资料清点与编码检查

对全部原始文件生成清单，记录：

- 相对路径、文件大小和校验值；
- 编码、换行符、字段分隔方式；
- 行数、列数分布和疑似表头；
- 空文件、重复文件和解析失败文件。

输出到 `reports/inventory.json`，不要修改原文件编码。

验收：

- 所有文件都有清点结果；
- 解析失败必须显式列出，不能静默跳过。

### 阶段 2：建立字段字典与原始层

先创建原始层，再创建业务层：

- 原始层逐行保存完整字段数组及来源位置；
- 业务层只提取已经确认含义的字段；
- 未确认列保留为原始 JSON，不自行命名成确定含义。

为每张重点来源表建立字段字典，注明“确认、推测、未知”。

验收：

- 规范化记录都能追溯到原始行；
- 未知字段没有被丢弃。

### 阶段 3：建立三类核心实体

按以下顺序处理：

1. 普通道具和任务道具；
2. 称号及称号组；
3. 宠物、骑宠配置与角色外形；
4. 技能、使用效果、图鉴等被引用实体。

重复 ID 的处理原则：

- 同一编号空间中的重复记录全部保留为来源版本；
- 选出的展示记录必须有确定的优先级；
- 名称冲突进入质量报告。

验收：

- ID 唯一性、来源完整性和外键检查通过；
- 重复与冲突数量可解释。

### 阶段 4：建立资源关系图

逐步建立：

- 道具 → 使用效果；
- 道具 → 宠物、称号或图鉴；
- 道具 → 配方、产物、随机包内容、商店；
- 宠物 → 外形、骑乘配置、技能；
- 称号 → 称号组、属性、授予来源；
- 所有资源 → 任务。

多跳关系应保留路径。例如“任务奖励宠物蛋 → 使用宠物蛋获得宠物”，页面可以显示为“可通过该任务奖励的宠物蛋获得”，不能简化成任务直接奖励宠物。

验收：

- 每条展示关系都能说明直接来源或完整路径；
- 孤立引用、缺失目标和循环关系进入报告。

### 阶段 5：处理图片与网页资源

原始资源、转换文件和网页发布文件分开管理：

```text
original_data/        # 权威输入
working_assets/       # 本地转换中间文件
public/generated/     # 可部署的网页缩略图
```

发布游戏图像前，应先确定项目的公开范围和版权说明。若决定暂不公开图片，首版可先显示名称、编号、说明和关系，不让图片处理阻塞数据整理。

验收：

- 页面和数据库中没有本机绝对路径；
- 缺图时有稳定占位样式；
- 转换脚本可重复运行。

### 阶段 6：生成面向网站的数据

不要让线上程序直接解析数万份原始文本。构建阶段生成轻量数据库或静态索引，线上只负责查询。

建议分成：

- `catalog.db`：本地完整规范数据库；
- `web_catalog.db` 或 D1 SQL：线上查询数据库；
- 搜索和筛选所需的预计算字段；
- 数据版本、构建时间和来源校验值。

验收：

- 连续构建两次得到相同的规范化内容；
- 数据库完整性和外键检查通过；
- 线上数据不含原始整行中不需要公开的内容。

### 阶段 7：实现访问者页面

建议首期页面：

- 总览；
- 道具列表与详情；
- 宠物／骑宠列表与详情；
- 称号列表与详情；
- 全站搜索；
- 关于资料。

详情页优先展示玩家关心的内容：是什么、有什么用、怎样获得、关联什么。内部字段和来源证据可放在折叠的“资料记录”区域。

任务关系使用普通链接：

```html
<a href="https://quests.xunxian.wiki/quests/1234">
  任务名称
</a>
```

验收：

- 手机和桌面端均可使用；
- 搜索结果可以复制链接并直接打开详情；
- 无效任务 ID 不产生死链接；
- 关联列表能区分奖励、要求、目标等语义。

### 阶段 8：测试与质量报告

至少包含：

- 解析器单元测试；
- 已知资源的回归测试；
- ID 空间隔离测试；
- 关系目标存在性测试；
- 任务交换文件 Schema 测试；
- 数据库外键和完整性测试；
- 搜索、筛选、分页与详情接口测试；
- 桌面端和移动端页面检查。

建议固定一些已人工核实的样本，例如：

- 一个具有明确任务奖励来源的普通道具；
- 一个任务目标使用的任务道具；
- 一个由道具获得的宠物；
- 一个具有骑乘配置和技能的骑宠；
- 一个由道具或任务授予的称号；
- 一个同数字 ID 分属不同资源类型的冲突样本。

### 阶段 9：版本发布

每次正式发布按以下顺序：

1. 确认工作区只有本次相关改动；
2. 运行完整测试；
3. 重建数据库和质量报告；
4. 检查数据版本及来源校验值；
5. 在预览环境检查页面；
6. 更新版本号和变更记录；
7. 部署数据库，再部署网站；
8. 检查线上搜索、详情和任务外链；
9. 最后创建 Git 提交。

部署产物应始终能由 Git 中的代码、配置、人工校订和本地 `original_data/` 重新生成。

## 八、建议的第一批交付物

第一阶段不要同时解释所有文件。建议依次完成：

1. 原始资料清单和字段字典；
2. 普通道具、任务道具、宠物、骑宠、称号五类基础表；
3. 道具使用效果以及道具获得宠物／称号的关系；
4. 任务资源交换文件和外链；
5. 搜索、列表和详情页；
6. 技能、图鉴、配方、商店和随机包等扩展关系；
7. 图片转换与发布。

这样可以先交付一个关系可靠、可检索的资料库，再逐步增加复杂字段，不需要在首版对 `original_data/` 中每一个未知列作出猜测。
