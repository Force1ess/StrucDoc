import asyncio
import json
from os.path import join as pjoin

from strucdoc import AsyncLLM, Document, get_tree_structure

# Configuration - Replace with your actual API credentials
api_key = "YOUR_API_KEY"
base_url = "YOUR_BASE_URL"  # e.g., "https://api.openai.com/v1" for OpenAI
model = "YOUR_MODEL"  # e.g., "gpt-4o" for OpenAI

# Initialize language and vision models
language_model = AsyncLLM(
    model=model,
    api_key=api_key,
    base_url=base_url,
)
vision_model = language_model  # Using the same model for both language and vision


async def parse_document():
    """
    Parse a markdown document and extract structured information using LLMs.

    This example demonstrates how to:
    1. Test LLM connections
    2. Parse a markdown document with images
    3. Extract structured sections, subsections, and media
    4. Save the results to JSON
    """
    # Test model connections
    if await language_model.test_connection() and await vision_model.test_connection():
        print("✅ Models are ready")
    else:
        print("❌ Models are not ready - check your API credentials")
        return

    # Path to your document directory (should contain source.md and images)
    pdf_dir = "Example-PPTAgent-MinerU"

    # Check if the example directory exists
    if not pjoin(pdf_dir, "source.md"):
        print(f"❌ Example directory '{pdf_dir}' not found or missing source.md")
        print(
            "Please ensure you have the example data or replace with your own markdown file"
        )
        return

    print(f"📄 Processing document from: {pdf_dir}")

    # Display document overview
    markdown = open(pjoin(pdf_dir, "source.md")).read()
    print("\n📋 Document Tree:")
    print(get_tree_structure(markdown, False))
    # Parse the document
    try:
        document = await Document.from_markdown(
            markdown,
            language_model,
            vision_model,
            pdf_dir,  # Directory containing images referenced in the markdown
            max_at_once=1,  # Process one section at a time to avoid rate limits
        )

        print("✅ Document parsed successfully!")
        print(f"📊 Found {len(document.blocks)} sections")

        # Save structured document to JSON
        output_file = "document.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(document.dict, f, indent=2, ensure_ascii=False)

        print(f"💾 Structured document saved to: {output_file}")

    except Exception as e:
        print(f"❌ Error processing document: {e}")
        print("Please check your API credentials and input files")


if __name__ == "__main__":
    print("🚀 Starting StructDoc Quick Start Example")
    print("=" * 50)
    asyncio.run(parse_document())
