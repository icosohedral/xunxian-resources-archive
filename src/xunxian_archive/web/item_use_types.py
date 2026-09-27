"""面向玩家的道具使用类型说明。

这里描述的是 ``item_use.txt`` 的一级执行类型，不是背包里的道具分类。
文案只解释已经能从官方资料交叉确认或高可信归纳的用途；参数不足时不猜测
具体数值或目标。
"""

from __future__ import annotations

from collections.abc import Sequence


ITEM_USE_TYPE_DESCRIPTIONS: dict[int, str] = {
    1: "添加状态或增益。",
    2: "收录风物志或图卷。",
    3: "调用通用脚本功能。",
    4: "传送到指定区域或返回绑定地点。",
    5: "执行技能或即时功能。",
    8: "写入或使用签名。",
    9: "开启随机礼包，并按对应掉落组发放物品。",
    10: "执行属性重置、修为或特殊成长操作。",
    11: "启动道具交互或对话。",
    12: "提升生活专业等级。",
    13: "学习生产配方。",
    14: "治疗角色受伤值。",
    15: "执行宠物笼或宠物蛋相关操作；具体功能尚待确认。",
    16: "使用清心符解除特定状态。",
    17: "使用画影图形；具体功能尚待确认。",
    18: "应用符纸、附魔、幻化或其他服务效果。",
    19: "强化神兵或为神兵附魔。",
    21: "使用天晶石、凝仙石等材料；具体功能尚待确认。",
    22: "风物志资料中的占位效果。",
    23: "使用唤云葫芦；具体功能尚待确认。",
    24: "使用唤云仙丹；具体功能尚待确认。",
    27: "增加角色经验。",
    28: "获得宠物。",
    29: "使用穿梭镜；具体功能尚待确认。",
    30: "使用化身大法；具体功能尚待确认。",
    32: "使用动画纸。",
    33: "使用动画橡皮。",
    34: "学习人物主动技能。",
    38: "学习坐骑被动技能。",
    39: "学习侍宠被动技能。",
    40: "执行宠物培养、进化、战魂或其他宠物系统功能。",
    41: "鉴定宠物蛋。",
    43: "获得或激活骑乘配置。",
    44: "开启已经废弃的仙缘宝鉴。",
    45: "降低角色犯罪值。",
    46: "定位罪犯。",
    47: "将罪犯打下坐骑。",
    48: "启用 PVP 保护锁。",
    49: "强化宠物蛋或神宠蛋。",
    50: "使用缩地成寸。",
    51: "增加家族人数上限。",
    53: "执行门派活动符或门派相关功能；具体功能尚待确认。",
    54: "使用门派印记。",
    55: "召唤指定 NPC 或修道者。",
    56: "应用一组预设状态或增益。",
    57: "使用超级家族印记。",
    58: "使用超级门派印记。",
    59: "开启一锁、三锁或九锁宝箱。",
    60: "将家族转换为门派。",
    61: "使用生死状或决斗契约。",
    62: "执行一集丹经验类操作；具体功能尚待确认。",
    63: "创建空白化身符。",
    64: "固化化身。",
    65: "获得临时化身。",
    66: "获得永久化身。",
    67: "增加化身生命。",
    68: "启用化身伪装。",
    69: "变成指定怪物。",
    70: "改变角色外形或性别。",
    71: "添加高级捉宠辅助状态。",
    72: "执行门派服务折扣、建筑或设施功能；具体功能尚待确认。",
    73: "执行返虚操作。",
    74: "为装备镶嵌宝石或开孔。",
    75: "使用补天石修复或强化；具体功能尚待确认。",
    76: "开启钱箱。",
    77: "执行飘羽仙丹属性点操作。",
    78: "执行点金、降龙或化灵转换。",
    79: "使用正气诀；具体功能尚待确认。",
    81: "使用强力诀；具体功能尚待确认。",
    82: "学习心法技能。",
    83: "使用祈福诀获得固定奖励。",
    84: "执行时装转换、包裹扩容等专用操作；具体功能取决于道具。",
    85: "制造、升级或转换灵宝；具体功能取决于道具。",
    86: "增加凝魂修炼值。",
    87: "使用玉剪处理装备或时装；具体功能取决于道具。",
    88: "在侍宠或骑宠之间转换外形。",
    89: "使用黄金锁。",
    90: "使用黄金钥匙。",
    91: "增加农政或家园点数。",
    92: "学习灵宝仙诀。",
    93: "扩展灵宝被动技能槽。",
    94: "使用门派徽记或列位标识。",
    95: "补偿角色属性点。",
    96: "还原神宠蛋。",
    97: "对神宠蛋执行转灵。",
    98: "使用仙玉凭证。",
    99: "移除装备或武器咒符。",
    100: "修改角色名称。",
    102: "使用三字天书；具体功能尚待确认。",
    103: "升级无字经、有字天书等经书。",
    104: "改变骑宠染色、血脉或外观。",
    105: "使用心法天书；具体功能尚待确认。",
    106: "使用金风仙苗；具体功能尚待确认。",
    107: "转换 VIP 或至尊符。",
    108: "转移装备开光孔。",
    109: "使用赤金诀、紫金诀转移孔位。",
    111: "鉴定或点化配饰符纸。",
    113: "使用门派任贤或举廉印记。",
    114: "转移时装属性。",
    115: "修改家族或门派名称。",
    116: "转换配饰外形。",
    117: "为时装充能。",
    118: "分解时装或强力诀。",
    119: "将三级时装升级为四级时装。",
    120: "点化通神诀。",
    121: "使用聚气灵剪；具体功能尚待确认。",
    122: "增加神运或幸运数值。",
    123: "打开传奇装备图纸界面。",
    124: "使用超级大喇叭或助威喇叭。",
    125: "重新生成传奇装备属性。",
    126: "精练装备。",
    127: "打开装备精练界面。",
    128: "增加修为。",
    129: "增加天书或经书经验，或为其升级。",
    130: "执行乾坤修复。",
    131: "转换仙魔武器。",
    132: "强化武器或装备。",
    133: "使用鞋子强力诀；具体功能尚待确认。",
    134: "使用超级修为仙丹。",
    135: "使用浑天石；具体功能尚待确认。",
    137: "执行纹玉切割或动态钥匙宝箱逻辑；具体功能尚待确认。",
    138: "按角色职业开启传奇装备礼包。",
    139: "使用破魂神丹。",
    141: "开启猎魂、妖魂或仙魄随机礼包。",
    142: "转换元神并保留等级。",
    143: "使用圆满或造化玉石。",
    145: "学习或激活战灵技能。",
    146: "将战灵归元或重置。",
    147: "使用灵福或祈福卷轴获得固定奖励。",
    148: "充值绑定仙玉。",
    149: "转换第三元神。",
    150: "执行新宝石点化、天衍或凝力；具体功能取决于道具。",
    151: "提取武魂。",
    152: "使用或注入武魂。",
    153: "使用万象宝盘；具体功能尚待确认。",
    154: "使用明王咒、附魔咒等为装备附加属性。",
    155: "使用汲灵玉吸取属性或能量。",
    156: "使用时装盘或时装进阶材料；具体功能尚待确认。",
    157: "打开曲灵玉界面。",
    158: "执行返虚、摄魂或仙魂操作。",
    159: "使用七夕同心锁；具体功能尚待确认。",
    161: "使用淬寒羽等材料提升品阶；具体功能取决于道具。",
    162: "执行附魔或附灵返虚。",
    163: "为装备附魔或附灵。",
    164: "喂养或提升宝石；具体功能尚待确认。",
    165: "执行灵符结晶、天晶或玄晶操作；具体功能取决于道具。",
    166: "开启神器或神器的新阶段。",
    167: "提升武器天赋上限。",
    168: "激活精灵。",
    169: "使用精灵蛋。",
    170: "开启或升级武器阵纹，或增加阵纹经验。",
    171: "使用水升卷或装备宝液升级；具体功能尚待确认。",
    172: "为灵宝开元。",
    173: "提取天机属性。",
    174: "为装备附加天机属性。",
    176: "解锁外观、时装或法宝幻化。",
    177: "使用无华玉璧；具体功能尚待确认。",
    178: "培养神器元灵、元魂、元魄或元精。",
    179: "参与奖池抽奖或使用幸运签。",
    180: "增加或转换特权卡片点数。",
    181: "铸炼装备或提取铸炼结果。",
    183: "增加玉牒玄晶经验。",
}


TYPE_3_SUBTYPE_DESCRIPTIONS = {
    18: "执行区域调查脚本",
    29: "对 NPC 使用道具或执行照妖脚本",
    104: "使用古宝图或藏宝图",
    124: "调用合并道具使用脚本",
    130: "使用迷宫传送符",
    158: "处理风水图小游戏碎片",
    353: "获得称号",
    420: "执行仙音符比赛功能",
    537: "开启脚本礼包",
    600: "召唤 NPC 或 BOSS",
    800: "执行收妖、收魂或法阵收集脚本",
    914: "执行动物或怪物相关脚本",
    947: "执行区域活动、防守或驱鬼脚本",
    1311: "开启活动或时限礼包",
    1367: "开启装备、职业或回归礼包",
    1368: "开启活动兑换礼包",
    1388: "应用幻化状态",
    1496: "执行休闲副本钓鱼功能",
    1501: "播放礼花或婚礼表现",
    1515: "使用节日食品",
    1553: "处理花草或活动采集物",
    1560: "播放喜宴或婚礼烟花",
    1712: "增加阵营或义军声望",
    1785: "使用 VIP 或商城积分卡",
    1906: "处理五行碎片或包袱皮",
    1939: "执行任务读条、张贴或采集事件",
    2044: "增加门派个人贡献",
    2139: "触发任务道具事件",
    2187: "执行七宝拂尘、仙鹤或桥梁等专用功能",
    2421: "执行足球动作",
    2477: "使用行者丹直升等级",
    2534: "处理活动材料",
    2850: "传送至场景站位",
}

TYPE_10_SUBTYPE_DESCRIPTIONS = {
    1: "洗去并重置全部角色属性点。",
    2: "洗去并重置全部抗性点。",
    3: "重置法宝天赋。",
    4: "激发一次奇遇。",
    6: "学习舞林秘笈。",
}

TYPE_10_ATTRIBUTES = {
    3: "力量",
    4: "体魄",
    5: "元神",
    6: "筋骨",
}

TYPE_40_ATTRIBUTES = {
    1: "力量",
    2: "体魄",
    3: "元神",
    4: "筋骨",
}


def _integer(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _parameter(parameters: Sequence[object], index: int) -> int | None:
    if index >= len(parameters):
        return None
    return _integer(parameters[index])


def _describe_type_3(parameters: Sequence[object]) -> str:
    subtype = _parameter(parameters, 0)
    if subtype is None:
        return ITEM_USE_TYPE_DESCRIPTIONS[3]
    action = TYPE_3_SUBTYPE_DESCRIPTIONS.get(subtype)
    if action is None:
        return f"调用脚本功能（二级操作 {subtype}）；具体行为由该脚本决定。"
    return f"{action}。"


def _describe_type_5(parameters: Sequence[object]) -> str:
    mode = _parameter(parameters, 0)
    first_value = _parameter(parameters, 1)
    second_value = _parameter(parameters, 2)
    if mode == 16:
        if first_value is not None:
            return f"恢复 {first_value:,} 点生命。"
        return "恢复生命；恢复量由效果参数决定。"
    if mode == 17:
        if first_value is not None and second_value is not None:
            return (
                f"恢复 {first_value:,} 点生命和 {second_value:,} 点法力。"
            )
        return "恢复生命和法力；恢复量由效果参数决定。"
    if mode is not None:
        return f"调用技能或即时功能 {mode}；具体表现由对应技能资料决定。"
    return ITEM_USE_TYPE_DESCRIPTIONS[5]


def _describe_type_10(parameters: Sequence[object]) -> str:
    mode = _parameter(parameters, 0)
    if mode in TYPE_10_SUBTYPE_DESCRIPTIONS:
        return TYPE_10_SUBTYPE_DESCRIPTIONS[mode]
    value = _parameter(parameters, 1)
    extra = _parameter(parameters, 2)
    if mode == 5:
        attribute = TYPE_10_ATTRIBUTES.get(value)
        if attribute is None:
            attribute = (
                f"属性编号 {value}" if value is not None else "指定属性"
            )
        if extra is not None:
            return f"局部重置{attribute}属性点；档位为 {extra}。"
        return f"局部重置{attribute}属性点。"
    if mode == 7:
        if value is not None:
            return f"增加 {value:,} 点修为或绿色属性点。"
        return "增加修为或绿色属性点。"
    if mode == 8:
        attribute = TYPE_10_ATTRIBUTES.get(value)
        if attribute is None:
            attribute = (
                f"属性编号 {value}" if value is not None else "指定属性"
            )
        return f"重置全部{attribute}属性点。"
    if mode == 9:
        if value is not None and extra is not None:
            return (
                f"增加特殊力量点数；点数种类编号为 {value}，"
                f"增加量为 {extra:,}。"
            )
        return "增加仙力、神力、圣力或玄力等特殊力量点数。"
    return ITEM_USE_TYPE_DESCRIPTIONS[10]


def _describe_type_18(parameters: Sequence[object]) -> str:
    return ITEM_USE_TYPE_DESCRIPTIONS[18]


def _describe_type_40(
    parameters: Sequence[object],
    effect_description: str | None,
) -> str:
    note = effect_description or ""
    first_value = _parameter(parameters, 0)
    second_value = _parameter(parameters, 1)
    third_value = _parameter(parameters, 2)

    if "经验" in note:
        if third_value is not None:
            return f"增加宠物经验 {third_value:,} 点。"
        return "增加宠物经验；经验量由效果参数决定。"
    if "新宠物战魂" in note:
        details = []
        if first_value is not None:
            details.append(f"战魂等级 {first_value}")
        if second_value is not None:
            details.append(f"魂灵 {second_value} 条")
        suffix = f"；{'，'.join(details)}。" if details else "。"
        return f"生成新版宠物战魂{suffix}"
    if "战魂" in note:
        return "执行宠物战魂的生成、培养、锁定或提取操作。"
    if "进化符" in note:
        attribute = TYPE_40_ATTRIBUTES.get(second_value)
        details = []
        if first_value is not None:
            details.append(f"{first_value} 阶")
        if attribute is not None:
            details.append(attribute)
        suffix = f"；{'，'.join(details)}。" if details else "。"
        return f"进化骑宠属性{suffix}"
    if "玩具" in note:
        return "使用宠物玩具。"
    if "洗点" in note or "还原" in note:
        return "重置宠物属性点或技能点。"
    if "解锁" in note:
        return "解除宠物锁定。"
    if "锁" in note:
        return "锁定宠物或宠物能力。"
    return ITEM_USE_TYPE_DESCRIPTIONS[40]


def describe_item_use_type(
    use_type_id: int | None,
    parameters: Sequence[object],
    effect_description: str | None = None,
) -> str:
    """返回可直接展示在道具详情页的使用类型说明。"""

    if use_type_id is None:
        return "原始资料未记录使用类型，暂时无法生成类型说明。"
    if use_type_id == 3:
        return _describe_type_3(parameters)
    if use_type_id == 5:
        return _describe_type_5(parameters)
    if use_type_id == 10:
        return _describe_type_10(parameters)
    if use_type_id == 18:
        return _describe_type_18(parameters)
    if use_type_id == 40:
        return _describe_type_40(parameters, effect_description)
    return ITEM_USE_TYPE_DESCRIPTIONS.get(
        use_type_id,
        f"当前资料尚未确认类型 {use_type_id} 的统一用途。",
    )
