"""validate_prerequisites 函数的单元测试"""

import pytest
from unittest.mock import patch, MagicMock
from app.agents.agent_context import validate_prerequisites


@pytest.fixture
def mock_db_session():
    """创建模拟的数据库会话 - 需要 patch app.database.SessionLocal"""
    with patch("app.database.SessionLocal") as mock_session_local:
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session
        yield mock_session


@pytest.fixture
def mock_chapter_outline(confirmed=True):
    """创建模拟的章节大纲"""
    mock = MagicMock()
    mock.confirmed = confirmed
    return mock


@pytest.fixture
def mock_world_setting(core_concept="测试世界观"):
    """创建模拟的世界观设定"""
    mock = MagicMock()
    mock.core_concept = core_concept
    return mock


class TestAllPrerequisitesMet:
    """测试所有前置条件都满足的情况"""

    def test_all_prerequisites_met(self, mock_db_session, mock_chapter_outline, mock_world_setting):
        """所有前置条件满足时，blocked 和 warnings 为空"""
        # 设置 mock 行为
        def query_side_effect(model):
            mock_q = MagicMock()
            model_name = model.__name__ if hasattr(model, '__name__') else str(model)
            
            if 'ChapterOutline' in model_name:
                mock_q.filter.return_value.first.return_value = mock_chapter_outline
            elif 'Character' in model_name:
                mock_q.filter.return_value.count.return_value = 3  # 有角色
            elif 'WorldSetting' in model_name:
                mock_q.filter.return_value.first.return_value = mock_world_setting
            elif 'Foreshadowing' in model_name:
                mock_q.filter.return_value.count.return_value = 2  # 有伏笔
            elif 'StyleConstraints' in model_name:
                mock_q.filter.return_value.first.return_value = MagicMock()
            elif 'PlotBlock' in model_name:
                mock_q.filter.return_value.count.return_value = 1
            elif 'Chapter' in model_name:
                mock_ch = MagicMock()
                mock_ch.content = "上一章内容"
                mock_q.filter.return_value.first.return_value = mock_ch
            elif 'EvolutionPlan' in model_name:
                mock_q.filter.return_value.count.return_value = 1
            elif 'TimelineEntry' in model_name:
                mock_q.filter.return_value.count.return_value = 1
            else:
                mock_q.filter.return_value.count.return_value = 0
            
            return mock_q

        mock_db_session.query.side_effect = query_side_effect

        result = validate_prerequisites(1, current_chapter=1)

        assert result["blocked"] == []
        assert result["warnings"] == []
        assert result["validated"] is True


class TestCharacterMissing:
    """测试角色缺失场景"""

    def test_missing_characters_blocked(self, mock_db_session, mock_chapter_outline, mock_world_setting):
        """角色缺失时，应加入 blocked"""
        def query_side_effect(model):
            mock_q = MagicMock()
            model_name = model.__name__ if hasattr(model, '__name__') else str(model)
            
            if 'ChapterOutline' in model_name:
                mock_q.filter.return_value.first.return_value = mock_chapter_outline
            elif 'Character' in model_name:
                mock_q.filter.return_value.count.return_value = 0  # 无角色
            elif 'WorldSetting' in model_name:
                mock_q.filter.return_value.first.return_value = mock_world_setting
            else:
                mock_q.filter.return_value.count.return_value = 1
                mock_q.filter.return_value.first.return_value = MagicMock()
            
            return mock_q

        mock_db_session.query.side_effect = query_side_effect

        result = validate_prerequisites(1, current_chapter=1)

        assert any(b["type"] == "character_missing" for b in result["blocked"])


class TestOutlineUnconfirmed:
    """测试大纲未确认场景"""

    def test_outline_unconfirmed_blocked(self, mock_db_session):
        """大纲未确认时，应加入 blocked"""
        mock_co = MagicMock()
        mock_co.confirmed = False

        def query_side_effect(model):
            mock_q = MagicMock()
            model_name = model.__name__ if hasattr(model, '__name__') else str(model)
            
            if 'ChapterOutline' in model_name:
                mock_q.filter.return_value.first.return_value = mock_co
            elif 'Character' in model_name:
                mock_q.filter.return_value.count.return_value = 1
            elif 'WorldSetting' in model_name:
                mock_q.filter.return_value.first.return_value = MagicMock(core_concept="测试")
            else:
                mock_q.filter.return_value.count.return_value = 1
                mock_q.filter.return_value.first.return_value = MagicMock()
            
            return mock_q

        mock_db_session.query.side_effect = query_side_effect

        result = validate_prerequisites(1, current_chapter=1)

        assert any(b["type"] == "outline_unconfirmed" for b in result["blocked"])


class TestOutlineMissing:
    """测试大纲不存在场景"""

    def test_outline_missing_blocked(self, mock_db_session):
        """大纲不存在时，应加入 blocked"""
        def query_side_effect(model):
            mock_q = MagicMock()
            model_name = model.__name__ if hasattr(model, '__name__') else str(model)
            
            if 'ChapterOutline' in model_name:
                mock_q.filter.return_value.first.return_value = None
            elif 'Character' in model_name:
                mock_q.filter.return_value.count.return_value = 1
            elif 'WorldSetting' in model_name:
                mock_q.filter.return_value.first.return_value = MagicMock(core_concept="测试")
            else:
                mock_q.filter.return_value.count.return_value = 1
                mock_q.filter.return_value.first.return_value = MagicMock()
            
            return mock_q

        mock_db_session.query.side_effect = query_side_effect

        result = validate_prerequisites(1, current_chapter=1)

        assert any(b["type"] == "chapter_outline_missing" for b in result["blocked"])


class TestWorldSettingMissing:
    """测试世界观缺失场景"""

    def test_world_setting_missing_blocked_no_ws(self, mock_db_session):
        """世界观不存在（返回 None）时，应加入 blocked"""
        def query_side_effect(model):
            mock_q = MagicMock()
            model_name = model.__name__ if hasattr(model, '__name__') else str(model)
            
            if 'ChapterOutline' in model_name:
                mock_q.filter.return_value.first.return_value = MagicMock(confirmed=True)
            elif 'Character' in model_name:
                mock_q.filter.return_value.count.return_value = 1
            elif 'WorldSetting' in model_name:
                mock_q.filter.return_value.first.return_value = None
            else:
                mock_q.filter.return_value.count.return_value = 1
                mock_q.filter.return_value.first.return_value = MagicMock()
            
            return mock_q

        mock_db_session.query.side_effect = query_side_effect

        result = validate_prerequisites(1, current_chapter=1)

        assert any(b["type"] == "world_setting_missing" for b in result["blocked"])

    def test_world_setting_missing_blocked_empty_core(self, mock_db_session):
        """世界观存在但 core_concept 为空时，应加入 blocked"""
        def query_side_effect(model):
            mock_q = MagicMock()
            model_name = model.__name__ if hasattr(model, '__name__') else str(model)
            
            if 'ChapterOutline' in model_name:
                mock_q.filter.return_value.first.return_value = MagicMock(confirmed=True)
            elif 'Character' in model_name:
                mock_q.filter.return_value.count.return_value = 1
            elif 'WorldSetting' in model_name:
                ws = MagicMock()
                ws.core_concept = None
                mock_q.filter.return_value.first.return_value = ws
            else:
                mock_q.filter.return_value.count.return_value = 1
                mock_q.filter.return_value.first.return_value = MagicMock()
            
            return mock_q

        mock_db_session.query.side_effect = query_side_effect

        result = validate_prerequisites(1, current_chapter=1)

        assert any(b["type"] == "world_setting_missing" for b in result["blocked"])


class TestNoCurrentChapter:
    """测试 current_chapter 为 None 的场景"""

    def test_no_current_chapter_skips_chapter_checks(self, mock_db_session):
        """current_chapter 为 None 时，应跳过章节相关检查"""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = MagicMock(core_concept="测试")
        mock_query.filter.return_value.count.return_value = 1
        mock_db_session.query.return_value = mock_query

        result = validate_prerequisites(1, current_chapter=None)

        chapter_types = {"chapter_outline_missing", "outline_unconfirmed", "previous_chapter_empty"}
        assert not any(b["type"] in chapter_types for b in result["blocked"])
        assert not any(w["type"] in chapter_types for w in result["warnings"])


class TestWarnings:
    """测试次要项警告"""

    def test_foreshadowing_empty_warning(self, mock_db_session, mock_chapter_outline, mock_world_setting):
        """伏笔为空时，应加入 warnings"""
        def query_side_effect(model):
            mock_q = MagicMock()
            model_name = model.__name__ if hasattr(model, '__name__') else str(model)
            
            if 'ChapterOutline' in model_name:
                mock_q.filter.return_value.first.return_value = mock_chapter_outline
            elif 'Character' in model_name:
                mock_q.filter.return_value.count.return_value = 1
            elif 'WorldSetting' in model_name:
                mock_q.filter.return_value.first.return_value = mock_world_setting
            elif 'Foreshadowing' in model_name:
                mock_q.filter.return_value.count.return_value = 0
            elif 'StyleConstraints' in model_name:
                mock_q.filter.return_value.first.return_value = MagicMock()
            elif 'PlotBlock' in model_name:
                mock_q.filter.return_value.count.return_value = 1
            elif 'Chapter' in model_name:
                mock_q.filter.return_value.first.return_value = MagicMock(content="test")
            elif 'EvolutionPlan' in model_name:
                mock_q.filter.return_value.count.return_value = 1
            elif 'TimelineEntry' in model_name:
                mock_q.filter.return_value.count.return_value = 1
            else:
                mock_q.filter.return_value.count.return_value = 0
            
            return mock_q

        mock_db_session.query.side_effect = query_side_effect

        result = validate_prerequisites(1, current_chapter=1)

        assert any(w["type"] == "foreshadowing_empty" for w in result["warnings"])


class TestErrorIsolation:
    """测试错误隔离"""

    def test_single_check_failure_does_not_affect_others(self, mock_db_session):
        """单项查询异常时，不影响其他检查项，结果应有 validated=True"""
        call_count = {"n": 0}

        def query_side_effect(model):
            call_count["n"] += 1
            mock_q = MagicMock()
            
            if call_count["n"] == 1:
                raise Exception("Database error")
            
            mock_q.filter.return_value.first.return_value = MagicMock(confirmed=True, core_concept="测��")
            mock_q.filter.return_value.count.return_value = 1
            return mock_q

        mock_db_session.query.side_effect = query_side_effect

        result = validate_prerequisites(1, current_chapter=1)

        assert result["validated"] is True
        assert "errors" in result
        assert len(result["errors"]) > 0


class TestPreviousChapterEmpty:
    """测试上一章内容为空"""

    def test_previous_chapter_empty_warning(self, mock_db_session, mock_world_setting):
        """上一章没有正文时，应加入 warning"""
        call_count = {"n": 0}

        def query_side_effect(model):
            call_count["n"] += 1
            mock_q = MagicMock()
            model_name = model.__name__ if hasattr(model, '__name__') else str(model)
            
            if 'ChapterOutline' in model_name:
                # 第一次是当前章节，第7次是上一章
                if call_count["n"] == 1:
                    mock_co = MagicMock()
                    mock_co.confirmed = True
                    mock_q.filter.return_value.first.return_value = mock_co
                else:
                    # 第7次 - 上一章大纲
                    mock_q.filter.return_value.first.return_value = MagicMock()
            elif 'Character' in model_name:
                mock_q.filter.return_value.count.return_value = 1
            elif 'WorldSetting' in model_name:
                mock_q.filter.return_value.first.return_value = mock_world_setting
            elif 'Foreshadowing' in model_name:
                mock_q.filter.return_value.count.return_value = 1
            elif 'StyleConstraints' in model_name:
                mock_q.filter.return_value.first.return_value = MagicMock()
            elif 'PlotBlock' in model_name:
                mock_q.filter.return_value.count.return_value = 1
            elif 'Chapter' in model_name:
                if call_count["n"] == 8:
                    # 上一章无正文
                    mock_q.filter.return_value.first.return_value = None
                else:
                    mock_q.filter.return_value.first.return_value = MagicMock(content="test")
            elif 'EvolutionPlan' in model_name:
                mock_q.filter.return_value.count.return_value = 1
            elif 'TimelineEntry' in model_name:
                mock_q.filter.return_value.count.return_value = 1
            else:
                mock_q.filter.return_value.count.return_value = 0
            
            return mock_q

        mock_db_session.query.side_effect = query_side_effect

        result = validate_prerequisites(1, current_chapter=2)

        assert any(w["type"] == "previous_chapter_empty" for w in result["warnings"])
