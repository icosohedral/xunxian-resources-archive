from xunxian_archive.web.item_use_types import (
    ITEM_USE_TYPE_DESCRIPTIONS,
    describe_item_use_type,
)


def test_all_documented_item_use_types_have_page_descriptions() -> None:
    assert len(ITEM_USE_TYPE_DESCRIPTIONS) == 162
    assert all(
        description.endswith("。")
        for description in ITEM_USE_TYPE_DESCRIPTIONS.values()
    )


def test_type_3_uses_known_secondary_operation() -> None:
    assert describe_item_use_type(3, ["537", "945"]) == "开启脚本礼包。"
    assert describe_item_use_type(3, ["1388", "446"]) == "应用幻化状态。"
    assert describe_item_use_type(3, ["9999"]) == (
        "调用脚本功能（二级操作 9999）；具体行为由该脚本决定。"
    )


def test_type_5_renders_recovery_values_and_skill_ids() -> None:
    assert describe_item_use_type(5, ["16", "1200"]) == (
        "恢复 1,200 点生命。"
    )
    assert describe_item_use_type(5, ["17", "600", "600"]) == (
        "恢复 600 点生命和 600 点法力。"
    )
    assert describe_item_use_type(5, ["327"]) == (
        "调用技能或即时功能 327；具体表现由对应技能资料决定。"
    )


def test_type_10_renders_fixed_growth_operations() -> None:
    assert describe_item_use_type(10, ["5", "3", "2"]) == (
        "局部重置力量属性点；档位为 2。"
    )
    assert describe_item_use_type(10, ["7", "5000"]) == (
        "增加 5,000 点修为或绿色属性点。"
    )
    assert describe_item_use_type(10, ["9", "2", "40"]) == (
        "增加特殊力量点数；点数种类编号为 2，增加量为 40。"
    )


def test_type_18_identifies_service_record_without_inventing_attributes() -> None:
    assert describe_item_use_type(18, ["628"]) == (
        "应用符纸、附魔、幻化或其他服务效果。"
    )


def test_type_40_uses_effect_note_to_choose_pet_operation() -> None:
    assert describe_item_use_type(
        40,
        ["1", "300", "2000"],
        "宠物经验丹",
    ) == "增加宠物经验 2,000 点。"
    assert describe_item_use_type(
        40,
        ["25", "5", "1"],
        "新宠物战魂",
    ) == "生成新版宠物战魂；战魂等级 25，魂灵 5 条。"
    assert describe_item_use_type(
        40,
        ["1", "1", "1", "5", "100"],
        "一阶力量进化符",
    ) == "进化骑宠属性；1 阶，力量。"


def test_missing_and_future_types_are_explicitly_unresolved() -> None:
    assert "未记录使用类型" in describe_item_use_type(None, [])
    assert describe_item_use_type(999, []) == (
        "当前资料尚未确认类型 999 的统一用途。"
    )
