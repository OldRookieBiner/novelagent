"""公共文本处理工具

供 retrieval.py（服务层）和 tools/utils.py（工具层）共用。
放在 app/utils/ 避免服务层依赖工具层的循环导入。
"""

_jieba_available = False


def tokenize_chinese(text: str) -> list[str]:
    """中文分词，jieba 不可用时退化为字符 bigram

    统一放在 app/utils/text.py，retrieval.py 和 tools/utils.py 共用。
    """
    global _jieba_available
    try:
        import jieba
        _jieba_available = True
        return list(jieba.cut(text))
    except ImportError:
        _jieba_available = False
        result = []
        for i in range(len(text) - 1):
            result.append(text[i:i+2])
        return result
