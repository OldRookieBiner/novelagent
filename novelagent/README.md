# NovelAgent

AI 小说创作 Agent 系统 - 三 Agent 协作完成小说创作流程

## 功能特性

- **大纲 Agent**：对话收集想法，生成大纲、卷纲、单元纲、章节纲
- **写作 Agent**：根据章节纲生成正文
- **审核 Agent**：检查一致性、质量、AI味、规则

## 完整创作流程

```
信息收集 → 大纲 → 卷纲 → 单元纲 → 章节纲 → 正文 → 审核 → 完成
```

## 安装

```bash
git clone https://github.com/OldRookieBiner/novelagent.git
cd novelagent
pip install -r requirements.txt
```

## 配置

设置 API Key 环境变量：

```bash
# 火山方舟 DeepSeek API
export DEEPSEEK_API_KEY="your-api-key"

# 或 OpenAI API
export OPENAI_API_KEY="your-api-key"
```

## 使用

```bash
# 创建新项目
python cli.py new "我的小说"

# 继续现有项目
python cli.py continue "我的小说"

# 查看项目列表
python cli.py list

# 查看项目状态
python cli.py status "我的小说"
```

## 对话命令

在对话中输入：
- `quit` - 退出并保存进度
- `status` - 查看项目状态
- `progress` - 查看写作进度

## 创作流程

1. **信息收集**：告诉 Agent 你想写什么小说
2. **生成大纲**：回复 `开始生成大纲`
3. **确认大纲**：回复 `确认大纲`
4. **生成卷纲**：回复 `确认卷纲`
5. **生成单元纲**：回复 `确认单元纲`
6. **生成章节纲**：回复 `确认章节纲`
7. **开始写作**：回复 `开始写作`
8. Agent 会自动：生成章节 → 审核 → 修改 → 继续下一章

## 技术栈

- Python 3
- 直接 LLM API 调用（无框架依赖）
- JSON 文件持久化

## 许可证

MIT License