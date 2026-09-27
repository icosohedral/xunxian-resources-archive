from xunxian_archive.models import ResourceKey, ResourceKind


def test_same_numeric_id_remains_distinct_across_required_spaces() -> None:
    keys = {
        ResourceKey(ResourceKind.ITEM, 1515),
        ResourceKey(ResourceKind.QUEST_ITEM, 1515),
        ResourceKey(ResourceKind.PET, 1515),
        ResourceKey(ResourceKind.TITLE, 1515),
    }

    assert len(keys) == 4
    assert {str(key) for key in keys} == {
        "item:1515",
        "quest_item:1515",
        "pet:1515",
        "title:1515",
    }


def test_negative_resource_id_is_rejected() -> None:
    try:
        ResourceKey(ResourceKind.ITEM, -1)
    except ValueError as exc:
        assert "non-negative" in str(exc)
    else:
        raise AssertionError("负数 ID 应被拒绝")

