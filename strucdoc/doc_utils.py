import re
from typing import Literal

from bs4 import BeautifulSoup
from fasttext import load_model
from huggingface_hub import hf_hub_download
from pydantic import BaseModel, Field, create_model

from .utils import Language, edit_distance

MARKDOWN_IMAGE_REGEX = re.compile(r"!\[.*\]\(.*\)")
MARKDOWN_TABLE_REGEX = re.compile(
    r"(\|.*\|)|((<html><body>)?<table>.*</table>(</body></html>)?)"
)

LID_MODEL = load_model(
    hf_hub_download(
        repo_id="julien-c/fasttext-language-id",
        filename="lid.176.bin",
    )
)


def language_id(text: str) -> Language:
    text = text[:1024].replace("\n", " ")
    label = LID_MODEL.predict(text)[0][0].replace("__label__", "")
    if label in ["zh", "ja", "ko"]:
        return Language.CJK
    else:
        return Language.LATIN


def count_markdown_chunks(markdown_text):
    """
    Count characters in each heading chunk of a Markdown document

    Args:
        markdown_text (str): Markdown text content

    Returns:
        list: List containing heading information and character counts
    """
    lines = markdown_text.split("\n")
    chunks = []
    current_heading = None
    current_content = []
    current_level = 0

    for line in lines:
        # Check if the line is a heading
        heading_match = re.match(r"^(#{1,6})\s+(.+)", line)

        if heading_match:
            # Save the previous chunk if exists
            if current_heading is not None:
                content_text = "\n".join(current_content)
                char_count = len(content_text.strip())
                chunks.append(
                    {
                        "level": current_level,
                        "heading": current_heading,
                        "char_count": char_count,
                        "content": content_text.strip(),
                    }
                )

            # Start a new chunk
            current_level = len(heading_match.group(1))
            current_heading = heading_match.group(2).strip()
            current_content = []
        else:
            # Non-heading line, add to current content
            current_content.append(line)

    # Handle the last chunk
    if current_heading is not None:
        content_text = "\n".join(current_content)
        char_count = len(content_text.strip())
        chunks.append(
            {
                "level": current_level,
                "heading": current_heading,
                "char_count": char_count,
                "content": content_text.strip(),
            }
        )

    return chunks


def calculate_hierarchical_counts(chunks):
    """
    Calculate character statistics including parent-child relationships

    Args:
        chunks (list): Original chunk list

    Returns:
        list: Chunk list with hierarchical statistics
    """

    def get_children_count(parent_index, parent_level):
        """Recursively calculate total character count of child headings"""
        total = 0
        for i in range(parent_index + 1, len(chunks)):
            current_level = chunks[i]["level"]

            # Stop if encountering same or higher level heading
            if current_level <= parent_level:
                break

            # Count all child direct character counts
            if current_level > parent_level:
                total += chunks[i]["char_count"]

        return total

    # Add hierarchical statistics to each chunk
    for i, chunk in enumerate(chunks):
        # Direct content character count
        chunk["direct_char_count"] = chunk["char_count"]

        # Children content character count
        children_count = get_children_count(i, chunk["level"])
        chunk["children_char_count"] = children_count

        # Total character count (self + all children)
        chunk["total_char_count"] = chunk["char_count"] + children_count

    return chunks


def display_results(chunks):
    """
    Format and display statistics results

    Args:
        chunks (list): Heading chunk list
    """
    print("Markdown Heading Character Statistics:")
    print("=" * 80)

    total_chars = 0
    root_total = 0

    for i, chunk in enumerate(chunks, 1):
        indent = "  " * (chunk["level"] - 1)
        heading_prefix = "#" * chunk["level"]

        print(f"{i}. {indent}{heading_prefix} {chunk['heading']}")
        print(f"   {indent}├─ Direct content: {chunk['direct_char_count']} characters")

        if chunk["children_char_count"] > 0:
            print(
                f"   {indent}├─ Children content: {chunk['children_char_count']} characters"
            )
            print(f"   {indent}└─ Total: {chunk['total_char_count']} characters")
        else:
            print(f"   {indent}└─ Total: {chunk['total_char_count']} characters")

        total_chars += chunk["direct_char_count"]

        if chunk["level"] == 1:
            root_total += chunk["total_char_count"]

        print()

    print("=" * 80)
    print(f"Total document characters: {total_chars}")
    print(f"Root level total: {root_total}")


def get_tree_structure(markdown: str, add_tag: bool = True):
    """
    Display tree structure statistics

    Args:
        markdown (str): Markdown content
    """
    chunks = count_markdown_chunks(markdown.strip())
    chunks_with_hierarchy = calculate_hierarchical_counts(chunks)

    tree = ""
    for chunk in chunks_with_hierarchy:
        indent = "  " * (chunk["level"] - 1)
        tree_symbol = "├─" if chunk["level"] > 1 else "■"
        if add_tag:
            heading = f"<title>{chunk['heading']}</title>"
        else:
            heading = chunk["heading"]

        tree += (
            f"{indent}{tree_symbol} {heading} "
            f"[Direct:{chunk['direct_char_count']} | Total Characters:{chunk['total_char_count']}]\n"
        )

    return tree


def split_markdown_by_headings(
    markdown_content: str,
    headings: list[str],
    adjusted_headings: list[str] = None,
    min_chunk_size: int = 64,
) -> list[str]:
    """
    Split markdown content using headings as separators.

    Args:
        markdown_content (str): The markdown content to split
        headings (list[str]): List of heading strings to split by
        adjusted_headings (list[str], optional): List of adjusted heading strings
        min_chunk_size (int, optional): Minimum chunk size. Defaults to 64.

    Returns:
        list[str]: List of content sections
    """

    if adjusted_headings:
        adjusted_headings = [
            max(headings, key=lambda x: edit_distance(x, ah))
            for ah in adjusted_headings
        ]
    else:
        adjusted_headings = headings

    sections = []
    current_section = []

    for line in markdown_content.splitlines():
        if any(line.strip().startswith(h) for h in adjusted_headings):
            if len(current_section) != 0:
                sections.append("\n".join(current_section).strip())
            current_section = [line]
        else:
            current_section.append(line)

    if len(current_section) != 0:
        sections.append("\n".join(current_section).strip())

    # if a chunk is too small, merge it with the previous chunk
    for i in reversed(range(1, len(sections))):
        if len(sections[i]) < min_chunk_size:
            sections[i - 1] += sections[i]
            sections.pop(i)

    if len(sections) > 1 and len(sections[0]) < min_chunk_size:
        sections[0] += sections[1]
        sections.pop(1)

    return sections


def process_markdown_content(
    markdown_content: str,
    max_chunk_size: int = 256,
):
    """
    Process markdown content into paragraphs and media elements.

    Args:
        markdown_content (str): The original markdown text
        max_chunk_size (int, optional): Maximum chunk size. Defaults to 256.
        table_regex (Pattern, optional): Regex to identify tables
        image_regex (Pattern, optional): Regex to identify images

    Returns:
        list: List of media elements with their context
    """
    paragraphs = []
    medias_chunks = []

    # Split text into paragraphs and identify media elements
    for i, para in enumerate(markdown_content.split("\n\n")):
        para = para.strip()
        if not para:
            continue

        paragraph = {"markdown_content": para, "index": i}

        if MARKDOWN_TABLE_REGEX.match(para):
            paragraph["type"] = "table"
            medias_chunks.append(paragraph)
        elif MARKDOWN_IMAGE_REGEX.match(para):
            paragraph["type"] = "image"
            medias_chunks.append(paragraph)
        else:
            paragraphs.append(paragraph)

    # Add context to each media element
    for media in medias_chunks:
        pre_chunk = ""
        after_chunk = ""

        # Get preceding context
        for chunk in paragraphs[: media["index"]]:
            pre_chunk += chunk["markdown_content"] + "\n\n"
            if len(pre_chunk) > max_chunk_size:
                break

        # Get following context
        for chunk in paragraphs[media["index"] + 1 :]:
            after_chunk += chunk["markdown_content"] + "\n\n"
            if len(after_chunk) > max_chunk_size:
                break

        media["near_chunks"] = (pre_chunk, after_chunk)

    return medias_chunks


def parse_table_with_merges(
    html: str,
) -> tuple[list[list[str]], list[tuple[int, int, int, int]]]:
    """parse table in html with merge cell

    Args:
        html (str)

    Returns:
        cell_and_merge (cell: list[list[str]], merges: list[(x0: int, y0: int, x1: int, y1: int)])
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    # Calculate maximum rows and columns of the table
    rows = table.find_all("tr")
    max_row = 0
    col_counter = []
    for row_idx, row in enumerate(rows):
        col_span_sum = 0
        for cell in row.find_all(["td", "th"]):
            row_span = int(cell.get("rowspan", 1))
            col_span = int(cell.get("colspan", 1))
            max_row = max(max_row, row_idx + row_span)
            col_span_sum += col_span
        col_counter.append(col_span_sum)
    max_col = max(col_counter) if col_counter else 0

    # Initialize data containers
    grid = [["" for _ in range(max_col)] for _ in range(max_row)]
    occupied = [[False for _ in range(max_col)] for _ in range(max_row)]
    merges = []

    # Main parsing logic
    for row_idx, row in enumerate(rows):
        col_idx = 0
        for cell in row.find_all(["td", "th"]):
            # Skip occupied columns
            while col_idx < max_col and occupied[row_idx][col_idx]:
                col_idx += 1
            if col_idx >= max_col:
                break

            # Parse cell attributes
            row_span = int(cell.get("rowspan", 1))
            col_span = int(cell.get("colspan", 1))
            cell_value = cell.get_text(strip=True)

            # Record merge range (closed interval)
            x0, y0 = row_idx, col_idx
            x1 = min(row_idx + row_span - 1, max_row - 1)
            y1 = min(col_idx + col_span - 1, max_col - 1)
            if not (x0 == x1 and y0 == y1):
                merges.append((x0, y0, x1, y1))

            # Fill top-left cell
            grid[x0][y0] = cell_value

            # Mark merged area as occupied
            for r in range(x0, x1 + 1):
                for c in range(y0, y1 + 1):
                    if r < max_row and c < max_col:
                        occupied[r][c] = True

            col_idx += col_span  # Move to next column
    return grid, merges


class LogicHeadings(BaseModel):
    headings: list[str]

    @classmethod
    def get_literal_schema(cls, allowed_headings: list[str]):
        return create_model(
            cls.__name__,
            headings=(list[Literal[tuple(allowed_headings)]], Field(...)),  # type: ignore
            __base__=BaseModel,
        )
