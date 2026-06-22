"""项目初始化各 generate_* 节点的结构化解析与入库测试

策略：mock LLM 的 chat_stream（异步生成器）+ 用 FakeKB 捕获写入，
不触碰真实 DB（KnowledgeBaseService 的 store 用 SessionLocal 连 PostgreSQL，
与 SQLite 测试夹具不兼容，故此处只验证解析/规整/入库参数）。
"""

import json
import pytest

from app.agents import initialization as init


# ========== 测试替身 ==========

class FakeStore:
    """通用捕获型 store：记录所有写入调用"""
    def __init__(self):
        self.created = []
        self._next_id = 1

    def _record(self, data):
        rec = dict(data)
        rec["id"] = self._next_id
        self._next_id += 1
        self.created.append(rec)
        return rec

    # 各 store 写入方法名不同，统一指向 _record
    def create(self, data): return self._record(data)
    def create_character(self, data): return self._record(data)
    def create_relation(self, data): return self._record(data)
    def create_constraints(self, data): return self._record(data)
    def upsert(self, data): return self._record(data)


class FakeKB:
    def __init__(self):
        self.world_setting = FakeStore()
        self.characters = FakeStore()
        self.outlines = FakeStore()
        self.foreshadowings = FakeStore()
        self.styles = FakeStore()


class FakeLLM:
    """按调用顺序返回预设响应的 chat_stream mock"""
    def __init__(self, response: str):
        self._response = response
        self.calls = []  # 捕获每次 chat_stream 收到的 messages，供 prompt 内容断言

    async def chat_stream(self, messages, **kwargs):
        self.calls.append(messages)
        # 分块吐出，模拟流式
        chunk = 64
        for i in range(0, len(self._response), chunk):
            yield self._response[i:i + chunk]


def fenced(payload) -> str:
    return "好的，以下是结果：\n```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"


# ========== 世界观 ==========

@pytest.mark.asyncio
async def test_world_setting_string_arrays():
    payload = {
        "core_concept": "灵气复苏的现代都市",
        "tiered_settings": {
            "red": ["凡人不可逆天改命"],
            "yellow": ["可短暂越级，代价是寿元折损"],
            "green": ["灵兽随主人情绪变色"],
        },
        "key_locations": ["青云宗：主角崛起的起点"],
    }
    kb = FakeKB()
    llm = FakeLLM(fenced(payload))
    ws_id, text = await init.generate_world_setting("种子", kb, llm, title="测试", outline_summary="概述")
    assert ws_id == 1
    created = kb.world_setting.created[0]
    # tiered 必须是字符串数组（前端按字符串渲染）
    for tier in ("red", "yellow", "green"):
        assert all(isinstance(x, str) for x in created["tiered_settings"][tier])
    assert all(isinstance(x, str) for x in created["key_locations"])


@pytest.mark.asyncio
async def test_world_setting_object_arrays_normalized_to_strings():
    # LLM 误产出对象数组，应被压成字符串
    payload = {
        "core_concept": "x",
        "tiered_settings": {
            "red": [{"rule": "不可违逆天道"}],
            "yellow": [{"rule": "可越级", "cost": "短命"}],
            "green": [],
        },
        "key_locations": [{"name": "青云宗", "description": "起点"}],
    }
    kb = FakeKB()
    llm = FakeLLM(fenced(payload))
    await init.generate_world_setting("种子", kb, llm)
    created = kb.world_setting.created[0]
    assert created["tiered_settings"]["red"] == ["不可违逆天道"]
    assert "短命" in created["tiered_settings"]["yellow"][0]
    assert created["key_locations"][0] == "青云宗：起点"


# ========== 角色（全字段，含三新列）==========

@pytest.mark.asyncio
async def test_characters_all_fields_including_new_columns():
    payload = [{
        "name": "林动", "role": "主角",
        "personality": "坚韧/重情",
        "catchphrase": "我命由我",
        "habit_action": "握拳",
        "deep_fear": "失去亲人",
        "core_motivation": "复兴家族",
        "growth_arc": "从废柴到强者",
        "appearance": "黑发少年",
        "backstory": "家道中落",
        "signature_item": "祖传石符",
        "knowledge_boundary": "不知道：石符来历；误以为：父亲已死",
        "speech_style": "直接/果断",
        "speech_samples": "你算什么东西｜我自己来",
    }]
    kb = FakeKB()
    llm = FakeLLM(fenced(payload))
    count, name_to_id, name_to_profile = await init.generate_characters("种子", "世界观文本", kb, llm, outline_text="大纲文本")
    assert count == 1
    assert name_to_id == {"林动": 1}
    c = kb.characters.created[0]
    assert c["knowledge_boundary"].startswith("不知道")
    assert c["speech_style"] == "直接/果断"
    assert "｜" in c["speech_samples"]
    assert c["role"] == "主角"


@pytest.mark.asyncio
async def test_characters_fallback_to_regex_on_bad_json():
    # JSON 解析失败 → 降级旧正则仍能产出角色，不抛异常
    markdown = (
        "## 林动\n"
        "- **角色定位**：主角\n"
        "- **核心动机**：复兴家族\n"
        "- **人物弧**：从废柴到强者\n"
        "- **说话风格**：直接果断\n"
    )
    kb = FakeKB()
    llm = FakeLLM(markdown)  # 无 json 代码块
    count, name_to_id, name_to_profile = await init.generate_characters("种子", "世界观", kb, llm)
    assert count >= 1
    assert "林动" in name_to_id


# ========== 关系 ==========

@pytest.mark.asyncio
async def test_relations_created_with_name_mapping():
    name_to_id = {"林动": 1, "应欢欢": 2}
    payload = [{
        "character_a_name": "林动", "character_b_name": "应欢欢",
        "relation_type": "感情", "direction": "双向",
        "current_status": "互生情愫", "trust_level": 70,
    }]
    kb = FakeKB()
    llm = FakeLLM(fenced(payload))
    n = await init.generate_relations(name_to_id, kb, llm)
    assert n == 1
    rel = kb.characters.created[0]
    assert rel["character_a_id"] == 1 and rel["character_b_id"] == 2
    assert rel["relation_type"] == "感情"
    assert rel["trust_level"] == 70


@pytest.mark.asyncio
async def test_relations_invalid_enum_coerced():
    name_to_id = {"甲": 1, "乙": 2}
    payload = [{
        "character_a_name": "甲", "character_b_name": "乙",
        "relation_type": "未知类型", "direction": "歪的",
        "current_status": "x", "trust_level": 999,
    }]
    kb = FakeKB()
    llm = FakeLLM(fenced(payload))
    n = await init.generate_relations(name_to_id, kb, llm)
    assert n == 1
    rel = kb.characters.created[0]
    assert rel["relation_type"] == "陌生"  # 非法枚举回退
    assert rel["direction"] == "双向"
    assert rel["trust_level"] == 100  # 越界裁剪


@pytest.mark.asyncio
async def test_relations_skip_when_too_few_characters():
    n = await init.generate_relations({"甲": 1}, FakeKB(), FakeLLM("[]"))
    assert n == 0


# ========== 风格（四字段全写）==========

@pytest.mark.asyncio
async def test_style_four_fields_written():
    payload = {
        "taboo_words": ["不禁", "竟然"],
        "forbidden_patterns": ["以……开头"],
        "style_anchor": "冷峻克制的示范文本",
        "abstract_rules": ["每段结尾不做总结"],
    }
    kb = FakeKB()
    llm = FakeLLM(fenced(payload))
    sid = await init.generate_style("种子", "大纲", "世界观", kb, llm)
    assert sid == 1
    c = kb.styles.created[0]
    assert c["taboo_words"] == ["不禁", "竟然"]
    assert c["forbidden_patterns"] == ["以……开头"]
    assert c["abstract_rules"] == ["每段结尾不做总结"]
    assert c["style_anchor"]


@pytest.mark.asyncio
async def test_style_fallback_stores_raw_as_anchor():
    kb = FakeKB()
    llm = FakeLLM("纯文本无 JSON 的风格说明")
    await init.generate_style("种子", "大纲", "世界观", kb, llm)
    c = kb.styles.created[0]
    assert "纯文本" in c["style_anchor"]
    assert c["taboo_words"] == []


# ========== 大纲 + 伏笔 ==========

@pytest.mark.asyncio
async def test_outline_json_parsed_and_foreshadowings_aggregated():
    payload = {
        "title": "逆天",
        "summary": "概述" * 10,
        "chapter_count_suggested": 25,
        "plot_points": [
            {"order": 1, "event": "开篇", "conflict": "c", "hook": "h",
             "foreshadowing_label": "V1", "foreshadowing_content": "石符暗藏血脉之力"},
            {"order": 8, "event": "强化", "conflict": "c", "hook": "h",
             "foreshadowing_label": "强化V1", "foreshadowing_content": "石符再次发烫"},
        ],
        "emotional_curve": "压抑 → 转折 → 高潮 → 释然",
        "theme": "命运与抗争",
    }
    kb = FakeKB()
    llm = FakeLLM(fenced(payload))
    oid, outline_data = await init.generate_outline("种子", kb, llm, target_words=125000)
    assert oid == 1
    assert outline_data["title"] == "逆天"
    assert outline_data["chapter_count_suggested"] == 25
    assert len(outline_data["plot_points"]) == 2
    # #2：characters 为死字段，upsert 入参不应再包含该键（角色由 Character 表承载）
    assert "characters" not in kb.outlines.created[0]

    n = await init.generate_foreshadowings(outline_data, kb)
    assert n == 2
    fs = kb.foreshadowings.created
    assert fs[0]["content"] == "石符暗藏血脉之力"
    assert fs[1]["level"] == "clue"  # "强化" → clue


@pytest.mark.asyncio
async def test_outline_fallback_to_regex():
    markdown = (
        "### 一、标题\n标题：《逆天》\n"
        "### 二、概述\n这是一段概述文本。\n"
        "### 四、情节节点\n1. 开篇 | 冲突 | 钩子 | V1\n"
    )
    kb = FakeKB()
    llm = FakeLLM(markdown)
    oid, outline_data = await init.generate_outline("种子", kb, llm, target_words=60000)
    assert oid == 1
    # 正则降级应至少拿到标题
    assert "逆天" in (outline_data.get("title") or "")
    # #2：降级路径同样不应写入 characters 死字段
    assert "characters" not in kb.outlines.created[0]


# ========== 问题 3：角色生成吃 plot_points（情节线索注入 prompt）==========

@pytest.mark.asyncio
async def test_characters_prompt_includes_plot_clue():
    payload = [{"name": "林动", "role": "主角"}]
    kb = FakeKB()
    llm = FakeLLM(fenced(payload))
    plot_points = [
        {"order": 1, "event": "林动觉醒石符", "conflict": "家族追杀", "hook": "石符异动"},
    ]
    count, name_to_id, name_to_profile = await init.generate_characters(
        "种子", "世界观文本", kb, llm, outline_text="大纲文本", plot_points=plot_points
    )
    assert count == 1
    # 角色 prompt 应包含情节线索摘要（事件 + 冲突 + 钩子）
    prompt_text = llm.calls[0][0]["content"]
    assert "情节线索" in prompt_text
    assert "林动觉醒石符" in prompt_text
    assert "家族追杀" in prompt_text
    assert "石符异动" in prompt_text


# ========== 问题 4：generate_characters 返回三元组 + 关系吃角色信息 ==========

@pytest.mark.asyncio
async def test_characters_return_triple_with_profile():
    payload = [{
        "name": "林动", "role": "主角",
        "core_motivation": "复兴家族", "personality": "坚韧",
    }]
    kb = FakeKB()
    llm = FakeLLM(fenced(payload))
    count, name_to_id, name_to_profile = await init.generate_characters("种子", "世界观", kb, llm)
    # name_to_id 结构不变（关系入库依赖），仍是 {name: id}
    assert name_to_id == {"林动": 1}
    # name_to_profile 携带 role/core_motivation/personality
    assert name_to_profile["林动"]["role"] == "主角"
    assert name_to_profile["林动"]["core_motivation"] == "复兴家族"
    assert name_to_profile["林动"]["personality"] == "坚韧"


@pytest.mark.asyncio
async def test_relations_prompt_includes_character_profile():
    name_to_id = {"林动": 1, "应欢欢": 2}
    name_to_profile = {
        "林动": {"role": "主角", "core_motivation": "复兴家族", "personality": "坚韧"},
        "应欢欢": {"role": "女主", "core_motivation": "守护宗门", "personality": "温婉"},
    }
    payload = [{
        "character_a_name": "林动", "character_b_name": "应欢欢",
        "relation_type": "感情", "direction": "双向",
        "current_status": "互生情愫", "trust_level": 70,
    }]
    kb = FakeKB()
    llm = FakeLLM(fenced(payload))
    n = await init.generate_relations(name_to_id, kb, llm, name_to_profile=name_to_profile)
    assert n == 1
    # 关系入库仍按 name_to_id 解析 id（未回归）
    rel = kb.characters.created[0]
    assert rel["character_a_id"] == 1 and rel["character_b_id"] == 2
    # 关系 prompt 升级为携带 role + 动机 + 性格
    prompt_text = llm.calls[0][0]["content"]
    assert "主角" in prompt_text
    assert "复兴家族" in prompt_text
    assert "坚韧" in prompt_text


# ========== 问题 5：入库字段白名单（_BaseStore._filter_writable 纯函数）==========

def test_filter_writable_drops_unknown_keys():
    from app.agents.services.stores.base import _BaseStore
    from app.models.character import Character

    data = {
        "name": "林动",
        "role": "主角",
        "unknown_field": "应被剔除",
        "id": 999,             # 系统维护列
        "project_id": 1,       # 外键，由 store 注入
        "created_at": "x",     # 时间戳
    }
    filtered = _BaseStore._filter_writable(Character, data)
    # 合法列保留
    assert filtered["name"] == "林动"
    assert filtered["role"] == "主角"
    # 未知键与系统维护列被剔除
    assert "unknown_field" not in filtered
    assert "id" not in filtered
    assert "project_id" not in filtered
    assert "created_at" not in filtered


def test_filter_writable_empty_data():
    from app.agents.services.stores.base import _BaseStore
    from app.models.character import Character
    assert _BaseStore._filter_writable(Character, {}) == {}


# ========== 问题 6：降级路径伏笔不清空且不产生垃圾条目 ==========

@pytest.mark.asyncio
async def test_fallback_foreshadowing_substantive_content_persisted():
    # 第 4 段含实质内容 → 去前缀后回填 content 并入库
    markdown = (
        "### 一、标题\n标题：《逆天》\n"
        "### 二、概述\n这是一段概述文本。\n"
        "### 四、情节节点\n"
        "1. 开篇 | 冲突 | 钩子 | V1: 石符暗藏血脉之力\n"
    )
    kb = FakeKB()
    llm = FakeLLM(markdown)
    oid, outline_data = await init.generate_outline("种子", kb, llm, target_words=60000)
    pp = outline_data["plot_points"][0]
    assert pp["foreshadowing"] == "V1: 石符暗藏血脉之力"  # 原始标签全文保留
    assert pp["foreshadowing_content"] == "石符暗藏血脉之力"  # 去前缀后回填

    n = await init.generate_foreshadowings(outline_data, kb)
    assert n == 1
    assert kb.foreshadowings.created[0]["content"] == "石符暗藏血脉之力"


@pytest.mark.asyncio
async def test_fallback_foreshadowing_pure_label_not_persisted():
    # 纯标签 V1（无实质内容）→ content 置空，不入库垃圾条目
    markdown = (
        "### 一、标题\n标题：《逆天》\n"
        "### 二、概述\n这是一段概述文本。\n"
        "### 四、情节节点\n"
        "1. 开篇 | 冲突 | 钩子 | V1\n"
    )
    kb = FakeKB()
    llm = FakeLLM(markdown)
    oid, outline_data = await init.generate_outline("种子", kb, llm, target_words=60000)
    pp = outline_data["plot_points"][0]
    assert pp["foreshadowing"] == "V1"           # 标签仍保留
    assert pp["foreshadowing_content"] == ""     # 纯标签不回填 content

    n = await init.generate_foreshadowings(outline_data, kb)
    assert n == 0  # 无实质内容，不入库
    assert kb.foreshadowings.created == []


# ========== theme 落地 + outline.world_setting 死字段移除 ==========

@pytest.mark.asyncio
async def test_outline_theme_persisted_and_no_world_setting_in_upsert():
    payload = {
        "title": "逆天",
        "summary": "概述" * 10,
        "chapter_count_suggested": 25,
        "plot_points": [],
        "emotional_curve": "压抑 → 高潮",
        "theme": "命运与抗争",
    }
    kb = FakeKB()
    llm = FakeLLM(fenced(payload))
    oid, outline_data = await init.generate_outline("种子", kb, llm, target_words=125000)
    upserted = kb.outlines.created[0]
    # theme 落地到 outline 专用列
    assert upserted["theme"] == "命运与抗争"
    # 死字段 world_setting 已从 upsert 入参移除（世界观由 WorldSetting 表承载）
    assert "world_setting" not in upserted


@pytest.mark.asyncio
async def test_outline_fallback_theme_key_present():
    markdown = (
        "### 一、标题\n标题：《逆天》\n"
        "### 二、概述\n这是一段概述文本。\n"
        "### 四、情节节点\n1. 开篇 | 冲突 | 钩子 | V1: 石符异动\n"
    )
    kb = FakeKB()
    llm = FakeLLM(markdown)
    oid, outline_data = await init.generate_outline("种子", kb, llm, target_words=60000)
    upserted = kb.outlines.created[0]
    # 降级路径 theme 键存在（置空），字段与 JSON 路径一致
    assert "theme" in upserted
    assert "world_setting" not in upserted


# ========== stream_initialization 集成测试 ==========

from unittest.mock import patch, MagicMock
import asyncio


class MultiFakeLLM:
    """按调用序号返回不同响应的 chat_stream mock

    每个响应可以是 str（正常返回）或 Exception（抛出）。
    """
    def __init__(self, responses: list):
        self._responses = responses
        self._call_idx = 0
        self.calls = []

    async def chat_stream(self, messages, **kwargs):
        self.calls.append(messages)
        idx = self._call_idx
        self._call_idx += 1
        if idx >= len(self._responses):
            # 超出预设时返回空串
            resp = ""
        else:
            resp = self._responses[idx]
        if isinstance(resp, Exception):
            raise resp
        chunk = 64
        for i in range(0, len(resp), chunk):
            yield resp[i:i + chunk]


class StreamFakeKB:
    """stream_initialization 专用 FakeKB，补全 update_story_seed"""
    def __init__(self):
        self.world_setting = FakeStore()
        self.characters = FakeStore()
        self.outlines = FakeStore()
        self.foreshadowings = FakeStore()
        self.styles = FakeStore()
        self.story_seed_saved = None

    def update_story_seed(self, seed):
        self.story_seed_saved = seed


async def _collect_events(gen):
    """收集异步生成器 yield 的所有 SSE 事件字符串"""
    events = []
    async for ev in gen:
        events.append(ev)
    return events


def _parse_event(ev_str):
    """从 SSE 字符串中解析 event type 和 data dict"""
    etype = ""
    data = {}
    for line in ev_str.strip().split("\n"):
        if line.startswith("event: "):
            etype = line[len("event: "):].strip()
        elif line.startswith("data: "):
            import json as _json
            try:
                data = _json.loads(line[len("data: "):].strip())
            except Exception:
                pass
    return etype, data


def _event_types(events):
    return [_parse_event(e)[0] for e in events]


def _final_status(events):
    """提取最后一个 init:done 事件的 status"""
    for ev in reversed(events):
        etype, data = _parse_event(ev)
        if etype == "init:done":
            return data.get("status", "")
    return ""


# 供各测试复用的成功响应数据
_SEED_RESP = "这是一个关于 AI 觉醒的故事种子"
_NAME_RESP = "机械之心"
_OUTLINE_RESP = fenced({
    "title": "机械之心",
    "summary": "AI 觉醒后与人类共存的科幻故事",
    "plot_points": [
        {"order": 1, "event": "AI 初次觉醒", "conflict": "自我认知", "hook": "觉醒的瞬间"},
    ],
    "emotional_curve": "好奇 → 冲突 → 和解",
    "theme": "意识与共存",
    "chapter_count_suggested": 12,
})
_WORLD_RESP = fenced({
    "core_concept": "近未来科技都市",
    "tiered_settings": {"red": ["不可篡改核心代码"], "yellow": [], "green": []},
    "key_locations": [{"name": "中央实验室", "description": "AI 诞生地"}],
})
_CHARS_RESP = fenced([
    {"name": "艾达", "role": "主角", "personality": "冷静", "core_motivation": "寻找自我"},
])
_STYLE_RESP = fenced({
    "taboo_words": ["不经大脑"],
    "forbidden_patterns": [],
    "style_anchor": "冷峻克制",
    "abstract_rules": [],
})
_RELATION_RESP = fenced([
    {"character_a_name": "艾达", "character_b_name": "博士", "relation_type": "信任", "direction": "双向", "trust_level": 60},
])


@pytest.mark.asyncio
async def test_outline_fail_terminates_partial():
    """大纲生成失败时，流程终止于 partial，不执行后续波次"""
    llm = MultiFakeLLM([_SEED_RESP, _NAME_RESP, Exception("outline LLM error")])
    kb = StreamFakeKB()
    fake_db = MagicMock()

    with patch("app.utils.llm.resolve_llm_service", return_value=llm), \
         patch("app.agents.initialization.KnowledgeBaseService", return_value=kb), \
         patch("app.agents.initialization.SessionLocal", return_value=fake_db):
        gen = init.stream_initialization(
            concept="AI 觉醒", target_words=60000,
            project_id=1, user_id=1,
        )
        events = await _collect_events(gen)

    types = _event_types(events)
    assert _final_status(events) == "partial"
    # 大纲失败后不应有世界观/角色事件
    assert "init:world" not in types
    assert "init:characters" not in types
    assert "init:style" not in types


@pytest.mark.asyncio
async def test_world_setting_fail_terminates_partial():
    """世界观生成失败时，流程终止于 partial，不执行角色/风格波次"""
    llm = MultiFakeLLM([_SEED_RESP, _NAME_RESP, _OUTLINE_RESP, Exception("world LLM error")])
    kb = StreamFakeKB()
    fake_db = MagicMock()

    with patch("app.utils.llm.resolve_llm_service", return_value=llm), \
         patch("app.agents.initialization.KnowledgeBaseService", return_value=kb), \
         patch("app.agents.initialization.SessionLocal", return_value=fake_db):
        gen = init.stream_initialization(
            concept="AI 觉醒", target_words=60000,
            project_id=1, user_id=1,
        )
        events = await _collect_events(gen)

    types = _event_types(events)
    assert _final_status(events) == "partial"
    assert "init:world" not in types
    assert "init:characters" not in types
    assert "init:style" not in types


@pytest.mark.asyncio
async def test_characters_fail_terminates_partial():
    """角色生成返回 0 个角色时，流程终止于 partial，不执行波次 4"""
    # 角色返回不可解析内容，generate_characters 内部降级解析也失败 → 返回 (0, {}, {})
    bad_chars_resp = "这是一段无法解析的角色文本，没有 JSON 也没有 Markdown 格式"
    llm = MultiFakeLLM([_SEED_RESP, _NAME_RESP, _OUTLINE_RESP, _WORLD_RESP, bad_chars_resp, _STYLE_RESP])
    kb = StreamFakeKB()
    fake_db = MagicMock()

    with patch("app.utils.llm.resolve_llm_service", return_value=llm), \
         patch("app.agents.initialization.KnowledgeBaseService", return_value=kb), \
         patch("app.agents.initialization.SessionLocal", return_value=fake_db):
        gen = init.stream_initialization(
            concept="AI 觉醒", target_words=60000,
            project_id=1, user_id=1,
        )
        events = await _collect_events(gen)

    types = _event_types(events)
    assert _final_status(events) == "partial"
    # 角色失败后不应有波次 4 相关事件（init:complete 是最终态）
    assert "init:complete" not in types


@pytest.mark.asyncio
async def test_style_fail_continues_to_complete():
    """风格生成失败时容错继续，最终返回 complete"""
    llm = MultiFakeLLM([
        _SEED_RESP, _NAME_RESP, _OUTLINE_RESP, _WORLD_RESP, _CHARS_RESP,
        Exception("style LLM error"), _RELATION_RESP,
    ])
    kb = StreamFakeKB()
    fake_db = MagicMock()

    with patch("app.utils.llm.resolve_llm_service", return_value=llm), \
         patch("app.agents.initialization.KnowledgeBaseService", return_value=kb), \
         patch("app.agents.initialization.SessionLocal", return_value=fake_db):
        gen = init.stream_initialization(
            concept="AI 觉醒", target_words=60000,
            project_id=1, user_id=1,
        )
        events = await _collect_events(gen)

    types = _event_types(events)
    assert _final_status(events) == "complete"
    # 应有 style error 事件
    assert "init:error" in types
    # 风格失败不影响最终完成
    assert "init:complete" in types


@pytest.mark.asyncio
async def test_all_success_returns_complete():
    """全部步骤成功时返回 complete，事件序列完整"""
    llm = MultiFakeLLM([
        _SEED_RESP, _NAME_RESP, _OUTLINE_RESP, _WORLD_RESP, _CHARS_RESP,
        _STYLE_RESP, _RELATION_RESP,
    ])
    kb = StreamFakeKB()
    fake_db = MagicMock()

    with patch("app.utils.llm.resolve_llm_service", return_value=llm), \
         patch("app.agents.initialization.KnowledgeBaseService", return_value=kb), \
         patch("app.agents.initialization.SessionLocal", return_value=fake_db):
        gen = init.stream_initialization(
            concept="AI 觉醒", target_words=60000,
            project_id=1, user_id=1,
        )
        events = await _collect_events(gen)

    types = _event_types(events)
    assert _final_status(events) == "complete"
    # 完整事件序列
    assert "init:start" in types
    assert "init:concept" in types
    assert "init:novel_name" in types
    assert "init:outline" in types
    assert "init:world" in types
    assert "init:characters" in types
    assert "init:style" in types
    assert "init:complete" in types
    assert "init:done" in types
