import json
import logging
import os
import traceback
from enum import Enum, auto
from itertools import product
from typing import Any

import json_repair
import Levenshtein
from bs4 import BeautifulSoup
from html2image import Html2Image
from mistune import html as markdown
from PIL import Image as PILImage
from tenacity import RetryCallState, retry, stop_after_attempt, wait_fixed


class Language(Enum):
    LATIN = auto()
    CJK = auto()


def get_logger(name="strucdoc", level=None):
    """
    Get a logger with the specified name and level.

    Args:
        name (str): The name of the logger.
        level (int): The logging level (default: logging.INFO).

    Returns:
        logging.Logger: A configured logger instance.
    """
    if level is None:
        level = int(os.environ.get("LOG_LEVEL", logging.INFO))

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Check if the logger already has handlers to avoid duplicates
    if not logger.handlers:
        # Create console handler and set level
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)

        # Create formatter
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
        )
        console_handler.setFormatter(formatter)

        # Add handler to logger
        logger.addHandler(console_handler)

    return logger


logger = get_logger(__name__)


def edit_distance(text1: str, text2: str) -> float:
    """
    Calculate the normalized edit distance between two strings.

    Args:
        text1 (str): The first string.
        text2 (str): The second string.

    Returns:
        float: The normalized edit distance (0.0 to 1.0, where 1.0 means identical).
    """
    if not text1 and not text2:
        return 1.0
    return 1 - Levenshtein.distance(text1, text2) / max(len(text1), len(text2))


def tenacity_log(retry_state: RetryCallState) -> None:
    """
    Log function for tenacity retries.

    Args:
        retry_state (RetryCallState): The retry state.
    """
    logger.warning("tenacity retry: %s", retry_state)
    traceback.print_tb(retry_state.outcome.exception().__traceback__)


def get_json_from_response(response: str) -> dict[str, Any]:
    """
    Extract JSON from a text response.

    Args:
        response (str): The response text.

    Returns:
        Dict[str, Any]: The extracted JSON.

    Raises:
        Exception: If JSON cannot be extracted from the response.
    """
    response = response.strip()

    try:
        return json.loads(response)
    except Exception:
        pass

    # Try to extract JSON from markdown code blocks
    l, r = response.rfind("```json"), response.rfind("```")
    if l != -1 and r != -1:
        json_obj = json_repair.loads(response[l + 7 : r].strip())
        if isinstance(json_obj, (dict, list)):
            return json_obj

    # Try to find JSON by looking for matching braces
    open_braces = []
    close_braces = []

    for i, char in enumerate(response):
        if char == "{" or char == "[":
            open_braces.append(i)
        elif char == "}" or char == "]":
            close_braces.append(i)

    for i, j in product(open_braces, reversed(close_braces)):
        if i > j:
            continue
        try:
            json_obj = json_repair.loads(response[i : j + 1])
            if isinstance(json_obj, (dict, list)):
                return json_obj
        except Exception:
            pass

    raise Exception("JSON not found in the given output", response)


# Create a tenacity decorator with custom settings
def tenacity_decorator(_func=None, *, wait: int = 3, stop: int = 5):
    def decorator(func):
        return retry(wait=wait_fixed(wait), stop=stop_after_attempt(stop))(func)

    if _func is None:
        # Called with arguments
        return decorator
    else:
        # Called without arguments
        return decorator(_func)


TABLE_CSS = """
table {
    border-collapse: collapse;  /* Merge borders */
    width: auto;               /* Width adapts to content */
    font-family: SimHei, Arial, sans-serif;  /* Font supporting Chinese characters */
    background: white;
}
th, td {
    border: 1px solid black;  /* Add borders */
    padding: 8px;             /* Cell padding */
    text-align: center;       /* Center text */
}
th {
    background-color: #f2f2f2; /* Header background color */
}
"""


# Convert Markdown to HTML
def markdown_table_to_image(markdown_text: str, output_path: str):
    """
    Convert a Markdown table to a cropped image

    Args:
    markdown_text (str): Markdown text containing a table
    output_path (str): Output image path, defaults to 'table_cropped.png'

    Returns:
    str: The path of the generated image
    """
    html = markdown(markdown_text)
    assert "table" in html, "Failed to find table in markdown"

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")
    html = f"<html><body>{''.join(str(table) for table in tables)}</body></html>"

    parent_dir, basename = os.path.split(output_path)
    hti = Html2Image(
        disable_logging=True,
        output_path=parent_dir,
        custom_flags=["--no-sandbox", "--headless"],
    )
    hti.browser.use_new_headless = None
    hti.screenshot(html_str=html, css_str=TABLE_CSS, save_as=basename)

    img = PILImage.open(output_path).convert("RGB")
    bbox = img.getbbox()
    assert (
        bbox is not None
    ), "Failed to capture the bbox, may be markdown table conversion failed"
    bbox = (0, 0, bbox[2] + 10, bbox[3] + 10)
    img.crop(bbox).save(output_path)
    return output_path


def package_join(*paths: str) -> str:
    """
    Join paths with the appropriate separator for the platform.

    Args:
        *paths: The paths to join.

    Returns:
        str: The joined path.
    """
    _dir = pdirname(__file__)
    return pjoin(_dir, *paths)


# Path utility functions
pjoin = os.path.join
pexists = os.path.exists
pbasename = os.path.basename
pdirname = os.path.dirname
