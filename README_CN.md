# StructDoc

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

[English](README.md) | 中文

**StructDoc** 是一个强大的工具，利用大型语言模型（LLM）智能地结构化和分析文档。它将包含嵌入式媒体的非结构化 Markdown 文档转换为组织良好、语义丰富的数据结构。

StructDoc 按层次结构组织文档：

```
Document
├── metadata (dict)
├── language (Language enum)
└── sections (list of Sections)
    └── Section
    |    ├── title (str)
    |    ├── summary (str)
    |    └── blocks (list of SubSections or Medias)
    └── ...
```

## ✨ 特性

- 🤖 **LLM 驱动分析**：利用最先进的语言和视觉模型
- 📄 **Markdown 处理**：解析包含嵌入图像和表格的复杂文档
- 🎯 **智能结构化**：自动提取章节、子章节和媒体
- 🖼️ **视觉能力**：使用多模态模型分析和为图像和表格生成标题
- 📊 **丰富输出**：生成包含元数据和摘要的结构化 JSON 输出
- 🔄 **异步处理**：高效的异步处理大型文档

## 🚀 安装

```bash
pip install -e .
```

## 🔑 设置

### API 配置

配置您的 LLM 提供商：

```python
from strucdoc import AsyncLLM

# OpenAI 兼容 API
llm = AsyncLLM(
    model="gpt-4o",
    api_key="your-api-key",
    base_url="https://api.openai.com/v1"
)
```

### 文档结构

按如下方式组织您的文件：

```
my-project/
├── document.md          # 您的 markdown 文件
├── figure1.png
├── table1.png
├── diagram.svg
└── output.json         # 生成的输出
```

## 📖 快速开始

### 基本用法

```python
import asyncio
from strucdoc import Document, AsyncLLM

async def main():
    # 初始化 LLM
    llm = AsyncLLM(
        model="gpt-4o",
        api_key="your-api-key",
        base_url="https://api.openai.com/v1"
    )

    # 读取 markdown 文件
    with open("document.md", "r") as f:
        markdown_content = f.read()

    # 处理文档
    document = await Document.from_markdown(
        markdown_content,
        language_model=llm,
        vision_model=llm,
        image_dir="images/",
        max_at_once=3  # 并发处理 3 个章节
    )

    # 保存结果
    import json
    with open("output.json", "w") as f:
        json.dump(document.dict, f, indent=2, ensure_ascii=False)

    print(f"✅ 已处理 {len(document.sections)} 个章节")

asyncio.run(main())
```

### 尝试示例

使用示例数据运行包含的示例：

```bash
# 首先在 quickstart.py 中配置您的 API 凭据
python quickstart.py
```

## 🔧 使用方法

### 处理结果

```python
from strucdoc.doc_utils import get_tree_structure

# 获取文档树
tree = get_tree_structure(markdown_content, False)
print(tree)

# 访问章节
for section in document.blocks:
    print(f"章节: {section.title}")
    print(f"摘要: {section.summary}")

# 获取文档概览
overview = document.get_overview(include_summary=True)
print(overview)

# 访问特定章节
intro_section = document["Introduction"]

# 通过标题查找媒体
image_path = document.find_caption("Figure 1: Overview")

# 检索特定内容
content = document.retrieve({
    "Introduction": ["Background", "Motivation"],
    "Methods": ["Data Collection"]
})
```

### 处理选项

```python
document = await Document.from_markdown(
    markdown_content,
    language_model=llm,
    vision_model=llm,
    image_dir="your-image-dir/",
    max_at_once=1  # 根据速率限制调整
)
```

## 📊 输出格式

StructDoc 生成结构化 JSON：

```json
{
  "metadata": {
    "title": "PPTAGENT: Generating and Evaluating Presentations Beyond Text-to-Slides",
    "presentation-date": "2025-05-26"
  },
  "sections": [
    {
      "title": "PPTAGENT: Generating and Evaluating Presentations Beyond Text-to-Slides",
      "summary": "本文档介绍了 PPTAGENT，这是一种受人类工作流程启发的新颖两阶段、基于编辑的高质量演示文稿生成方法。它分析参考演示文稿以提取功能类型和内容模式，然后为新幻灯片迭代生成编辑操作。文档还介绍了 PPTEVAL，这是一个评估框架，从内容、设计和连贯性三个维度评估演示文稿。实验表明，PPTAGENT 显著优于现有方法，在所有三个维度上都取得了优异的分数，并展示了具有自我纠正机制的强大生成性能。",
      "blocks": [
    ...
```

## 💡 提示

- 使用 `max_at_once=1` 避免速率限制
- 设置 `LOG_LEVEL` 为 `DEBUG` 查看更详细的日志
- 检查您的 LLM 是否准备就绪

## 🤝 贡献

我们欢迎贡献！请提交 Pull Request 或为错误和功能请求开启 issue。
