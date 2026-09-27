# 首批来源字段字典

状态只使用三种：**确认**、**推测**、**未知**。未知列继续保留在 `raw_values_json`，不会丢弃，也不会被赋予看似确定的业务名称。

| 来源 | 列（从 0 开始） | 暂定字段 | 状态 | 依据 |
|---|---:|---|---|---|
| `mb/item/item_list*.txt` | 0 | `resource_id` | 确认 | 文件表头“物品ID” |
| `mb/item/item_list*.txt` | 1 | `display_name` | 确认 | 文件表头“物品名称” |
| `mb/item/item_list*.txt` | 2 | `item_type_id` | 确认 | 文件表头“物品类” |
| `mb/item/item_list*.txt` | 4 | `icon_key` | 推测 | 表头为“道具图片”，尚未确认资源寻址规则 |
| `mb/item/item_list*.txt` | 5 | `model_id` | 确认 | 文件表头“模型ID” |
| `mb/item/item_list*.txt` | 6 | `text_id` | 确认 | 文件表头“文字介绍ID”；具体文本表的连接仍待补充 |
| `mb/item/item_list*.txt` | 7 | `quality` | 确认 | 文件表头“物品品质” |
| `mb/item/item_list*.txt` | 15 | `currency_is_tradable` | 确认 | 文件表头“流通金钱”；值为 1 时价格使用流通金，否则使用绑定金 |
| `mb/item/item_list*.txt` | 16 | `buy_price` | 确认 | 文件表头“购买价格”；基础单位为铜 |
| `mb/item/item_list*.txt` | 17 | `sell_price` | 确认 | 文件表头“售出价格”；基础单位为铜 |
| `mb/item/item_list*.txt` | 11 | `level_requirement` | 确认 | 文件表头“等级限制” |
| `mb/item/item_list*.txt` | 30 | `use_effect_raw` | 确认 | 文件表头“使用属性”；已验证为成对的使用效果 ID 与数量 |
| `mb/item/item_list*.txt` | 34 | `stack_limit` | 确认 | 文件表头“重叠数量” |
| `mb/quest/quest_item.txt` | 0 | `display_name` | 确认 | 与索引说明及样本结构一致 |
| `mb/quest/quest_item.txt` | 1 | `resource_id` | 确认 | 与任务道具引用方式一致 |
| `mb/quest/quest_item.txt` | 2 以后 | — | 未知 | 无表头，逐列语义尚未核实 |
| `mb/pet/pet_list.txt` | 0 | `display_name` | 确认 | 与索引说明及样本结构一致 |
| `mb/pet/pet_list.txt` | 1 | `resource_id` | 确认 | 宠物编号 |
| `mb/pet/pet_list.txt` | 2 | `character_id` | 推测 | 与 `cha_list` 样本交叉比对一致，尚缺正式表头 |
| `mb/pet/pet_list.txt` | 4 | `model_id` | 推测 | 与模型编号分布一致，尚缺正式表头 |
| `mb/pet/pet_list.txt` | 5 | `attribute_template_id` | 高可信 | 可稳定连接 `mb/pet/pet_model.txt` 第 1 列；模板包含力量、体魄、元神和筋骨四维值 |
| `mb/pet/pet_list.txt` | 6 | `ride_id` | 确认 | 与 `ride_list` 目标存在性及道具使用链交叉验证 |
| `mb/pet/pet_list.txt` | 8 | `note` | 推测 | 样本呈现为策划备注文本 |
| `mb/pet/pet_list.txt` | 3、7、9 以后 | — | 未知 | 原值完整保留 |
| `mb/etc/title_list.txt` | 0 | `display_name` | 确认 | 称号名称 |
| `mb/etc/title_list.txt` | 1 | `resource_id` | 确认 | 称号编号 |
| `mb/etc/title_list.txt` | 2 | `title_group_id` | 确认 | 连接 `mb/etc/title_group.txt` 第 1 列，页面显示对应分组名称而非内部编号 |
| `mb/etc/title_group.txt` | 2 | `title_group_family_id` | 高可信 | 数值 `1–10` 稳定形成称号分组的上级分类；原资料没有提供上级分类名称，网页中的中文名称为资料库按各组内容归纳 |
| `mb/etc/title_list.txt` | 5 | `active_attributes` | 确认 | 佩戴称号时生效；按“属性编号、数值形式、数值”三元组排列，属性编号连接 `mb/etc/atb_fight.txt` |
| `mb/etc/title_list.txt` | 7 | `description` | 确认 | 连续自然语言说明文本 |
| `mb/etc/title_list.txt` | 8 | `acquisition_hint` | 确认 | 连续自然语言获得条件 |
| `mb/etc/title_list.txt` | 10 | `passive_attributes` | 确认 | 获得称号后生效；格式及属性编号连接方式同主动属性 |
| `mb/etc/title_list.txt` | 3–4、6、9、11 以后 | — | 未知 | 排序、外观、时限等字段仍需跨表验证 |
| `mb/object/ride_list.txt` | 0 | `display_name` | 确认 | 骑乘配置名称 |
| `mb/object/ride_list.txt` | 1 | `resource_id` | 确认 | 骑乘配置编号 |
| `mb/object/ride_list.txt` | 2 | `character_id` | 推测 | 与角色编号分布一致，仍需结合 `ride_connection.txt` 验证 |
| `mb/object/ride_list.txt` | 16–21 | `ride_skill_ids` | 确认 | 六个技能槽；选中版本共 1,497 次引用，1,460 次能命中技能定义 |
| `mb/object/ride_list.txt` | 3–15、22 以后 | — | 未知 | 动作、速度及状态字段尚未确认 |
| `mb/pet/car_skill.txt` | 0 | `display_name` | 确认 | `index_list.txt` 明确标为“坐骑技能表” |
| `mb/pet/car_skill.txt` | 1 | `skill_id` | 确认 | 被 `ride_list` 技能槽稳定引用 |
| `mb/pet/car_skill.txt` | 2–3 | — | 未知 | 数值形态稳定，但单位与业务语义尚未核实 |
| `mb/pet/car_skill.txt` | 4 | `internal_note` | 确认 | 多为动作、对象或测试用短备注，不作为玩家效果说明 |
| `mb/skill/skill_data_npc*.txt` | 0 | `display_name` | 确认 | 技能名称 |
| `mb/skill/skill_data_npc*.txt` | 1 | `skill_id` | 确认 | 补充解析新版坐骑技能槽引用 |
| `mb/skill/skill_data_npc*.txt` | 3 | `icon_key` | 推测 | 值形态与技能图标键一致 |
| `mb/skill/skill_data_npc*.txt` | 4 | `description` | 确认 | 玩家可读的技能说明 |
| `mb/item/item_use.txt` | 0 | `effect_id` | 确认 | 被 `item_list`“使用属性”稳定引用 |
| `mb/item/item_use.txt` | 1 | `use_type_id` | 推测 | 不同数值对应稳定参数形态；类型枚举未完整命名 |
| `mb/item/item_use.txt` | 2–19 | `parameters` | 未知 | 按原顺序保留，不为未知参数强行命名 |
| `mb/item/item_use.txt` | 20 | `description` | 确认 | 自然语言使用效果说明 |
| `mb/item/item_pet.txt` | 1 | `item_id` | 确认 | 能稳定命中普通道具编号，用作宠物产出链的佐证 |
| `mb/etc/itemaddtitle.txt` | 1 | `mapping_id` | 确认 | 被称号类使用效果参数引用 |
| `mb/etc/itemaddtitle.txt` | 3 | `title_id` | 确认 | 能稳定命中称号编号 |

## 仍需确认

- `quest_item.txt` 与 `quest_item_ex.txt` 的覆盖、扩展或版本关系；
- `item_use.txt` 各使用类型及参数槽的完整枚举语义；
- 普通道具到宠物关系中，`item_pet.txt` 仍有 274 条无法通过骑乘编号匹配宠物；
- `pet_list.txt` 中角色 ID、模型 ID 和宠物种类列的正式字段依据；
- `ride_list.txt`、`ride_connection.txt` 与 `cha_list.txt` 的主外键方向；
- 坐骑技能仍有 37 次引用没有定义，涉及 13 个当前选中版本中的技能编号；
- 已解析的 1,111 个坐骑技能中，30 个仍没有玩家可读的完整效果说明；
- `car_skill.txt` 第 2–3 列的数值单位，以及多个 NPC 技能表出现同号定义时的版本优先级；
- `title_list.txt` 的称号组及其余展示控制列；
- 任务交换文件中的 459 条任务道具引用和 4 条称号引用在当前资源范围内没有目标；
- `item_list2.txt` 第 36 列与其他分表同位置字段的版本差异。
