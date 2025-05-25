import os

import pytest

from strucdoc import AsyncLLM, Document, package_join

TESTDOC = package_join("..", "Example-PPTAgent-MinerU")
language_model = AsyncLLM(
    model=os.environ.get("LANGUAGE_MODEL"),
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url=os.environ.get("API_BASE"),
)
vision_model = AsyncLLM(
    model=os.environ.get("VISION_MODEL"),
    api_key=os.environ.get("OPENAI_API_KEY"),
    base_url=os.environ.get("API_BASE"),
)


@pytest.mark.asyncio
@pytest.mark.llm
async def test_document_async():
    with open(f"{TESTDOC}/source.md") as f:
        markdown_content = f.read()
    cutoff = markdown_content.find("## When (and when not) to use agents")
    image_dir = TESTDOC
    await Document.from_markdown(
        markdown_content[:cutoff],
        language_model,
        vision_model,
        image_dir,
    )
