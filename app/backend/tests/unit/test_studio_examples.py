"""后端-单元：services/studio_examples.py 的示例匹配与三件套结构。

纯函数，不连接数据库、不发网络请求。
"""
from services import studio_examples
from services.studio_validation import (
    validate_artifact_html,
    validate_outline_payload,
    validate_plan_payload,
)

EXACT = [
    ("一个记录每日饮水量的追踪器，带进度环", "hydration"),
    ("团队任务看板，支持新增、拖动状态、筛选", "kanban"),
    ("个人记账本，按分类统计月度支出", "ledger"),
    ("读书笔记库，支持标签和搜索", "notes"),
]


def test_match_example_exact():
    for text, expected_id in EXACT:
        example = studio_examples.match_example(text)
        assert example is not None
        assert example["id"] == expected_id

    # 容忍首尾空白
    assert studio_examples.match_example("  一个记录每日饮水量的追踪器，带进度环  ")["id"] == "hydration"


def test_match_example_keywords():
    assert studio_examples.match_example("帮我做一个喝水提醒的小工具")["id"] == "hydration"
    assert studio_examples.match_example("需要一个拖拽卡片的任务板")["id"] == "kanban"
    assert studio_examples.match_example("记录每天开销的记账工具")["id"] == "ledger"
    assert studio_examples.match_example("给读书做笔记并加标签")["id"] == "notes"


def test_match_example_miss():
    assert studio_examples.match_example("") is None
    assert studio_examples.match_example("一个完全无关的天气应用") is None


def test_fixture_example_returns_matching_html():
    html_by_id = {e["id"]: e["html"] for e in studio_examples.EXAMPLES}
    for text, expected_id in EXACT:
        fixture = studio_examples.fixture(text)
        assert fixture["html"] == html_by_id[expected_id]


def test_fixture_miss_returns_generic():
    fixture = studio_examples.fixture("天气应用")
    assert fixture["html"] == studio_examples.GENERIC_HTML
    assert fixture["plan"]["summary"] == "演示通用可交互原型"


def test_all_examples_pass_validation():
    for example in studio_examples.EXAMPLES:
        validate_plan_payload(example["plan"])
        validate_outline_payload(example["outline"])
        validate_artifact_html(example["html"])

    generic = studio_examples.generic_fixture()
    validate_plan_payload(generic["plan"])
    validate_outline_payload(generic["outline"])
    validate_artifact_html(generic["html"])


def test_fixture_returns_deterministic_payloads():
    a = studio_examples.fixture("个人记账本，按分类统计月度支出")
    b = studio_examples.fixture("个人记账本，按分类统计月度支出")
    assert a == b
    assert a["plan"] == b["plan"]
    assert a["outline"] == b["outline"]