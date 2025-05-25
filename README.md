# StructDoc

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

English | [中文](README_CN.md)

**StructDoc** is a powerful tool for utilizing Large Language Models (LLMs) to intelligently structure and analyze documents. It transforms unstructured markdown documents with embedded media into well-organized, semantically rich data structures.

StructDoc organizes documents hierarchically:

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

## ✨ Features

- 🤖 **LLM-Powered Analysis**: Leverage state-of-the-art language and vision models
- 📄 **Markdown Processing**: Parse complex documents with embedded images and tables
- 🎯 **Intelligent Structuring**: Automatically extract sections, subsections, and media
- 🖼️ **Vision Capabilities**: Analyze and caption images and tables using multimodal models
- 📊 **Rich Output**: Generate structured JSON output with metadata and summaries
- 🔄 **Async Processing**: Efficient asynchronous processing for large documents

## 🚀 Installation

```bash
pip install -e .
```

## 🔑 Setup

### API Configuration

Configure your LLM provider:

```python
from strucdoc import AsyncLLM

# OpenAI-compatible API
llm = AsyncLLM(
    model="gpt-4o",
    api_key="your-api-key",
    base_url="https://api.openai.com/v1"
)
```

### Document Structure

Organize your files like this:

```
my-project/
├── document.md          # Your markdown file
├── figure1.png
├── table1.png
├── diagram.svg
└── output.json         # Generated output
```

## 📖 Quick Start

### Basic Usage

```python
import asyncio
from strucdoc import Document, AsyncLLM

async def main():
    # Initialize LLM
    llm = AsyncLLM(
        model="gpt-4o",
        api_key="your-api-key",
        base_url="https://api.openai.com/v1"
    )

    # Read markdown file
    with open("document.md", "r") as f:
        markdown_content = f.read()

    # Process document
    document = await Document.from_markdown(
        markdown_content,
        language_model=llm,
        vision_model=llm,
        image_dir="images/",
        max_at_once=3  # Process 3 sections concurrently
    )

    # Save results
    import json
    with open("output.json", "w") as f:
        json.dump(document.dict, f, indent=2, ensure_ascii=False)

    print(f"✅ Processed {len(document.sections)} sections")

asyncio.run(main())
```

### Try the Example

Run the included example with sample data:

```bash
# Configure your API credentials in quickstart.py first
python quickstart.py
```

## 🔧 Usage

### Working with Results

```python
from strucdoc.doc_utils import get_tree_structure

# Access sections
for section in document.blocks:
    print(f"Section: {section.title}")
    print(f"Summary: {section.summary}")

# Get document tree
print(get_tree_structure(markdown_content, False))

# Get document overview
overview = document.get_overview(include_summary=True)
print(overview)

# Access specific sections
intro_section = document["Introduction"]

# Find media by caption
image_path = document.find_caption("Figure 1: Overview")

# Retrieve specific content
content = document.retrieve({
    "Introduction": ["Background", "Motivation"],
    "Methods": ["Data Collection"]
})
```

### Processing Options

```python
document = await Document.from_markdown(
    markdown_content,
    language_model=llm,
    vision_model=llm,
    image_dir="your-image-dir/",
    max_at_once=1  # Adjust for rate limiting
)
```

## 📊 Output Format

StructDoc generates structured JSON:

```json
{
  "metadata": {
    "title": "PPTAGENT: Generating and Evaluating Presentations Beyond Text-to-Slides",
    "presentation-date": "2025-05-26"
  },
  "sections": [
    {
      "title": "PPTAGENT: Generating and Evaluating Presentations Beyond Text-to-Slides",
      "summary": "This document introduces PPTAGENT, a novel two-stage, edit-based approach for generating high-quality presentations inspired by human workflows. It analyzes reference presentations to extract functional types and content schemas, then iteratively generates editing actions for new slides. The document also presents PPTEVAL, an evaluation framework assessing presentations across Content, Design, and Coherence dimensions. Experiments show PPTAGENT significantly outperforms existing methods, achieving superior scores in all three dimensions and demonstrating robust generation performance with self-correction mechanisms.",
      "blocks": [
    ...
```

## 💡 Tips

- Use `max_at_once=1` to avoid rate limits
- Set `LOG_LEVEL` to `DEBUG` to see more detailed logs
- Check if your llms is ready to use

## 🤝 Contributing

We welcome contributions! Please submit Pull Requests or open issues for bugs and feature requests.
