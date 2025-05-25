import hashlib
import re
from typing import Optional

from jinja2 import Environment, StrictUndefined
from mistune import html as markdown
from PIL import Image
from pydantic import BaseModel, field_validator

from .llms import AsyncLLM
from .utils import (
    edit_distance,
    get_logger,
    markdown_table_to_image,
    package_join,
    pexists,
    pjoin,
)
from .doc_utils import parse_table_with_merges

env = Environment(undefined=StrictUndefined)

IMAGE_PARSING_REGEX = re.compile(r"\((.*?)\)")
TABLE_CAPTION_PROMPT = env.from_string(
    open(package_join("prompts", "markdown_table_caption.txt")).read()
)
IMAGE_CAPTION_PROMPT = env.from_string(
    open(package_join("prompts", "markdown_image_caption.txt")).read()
)

logger = get_logger(__name__)


class Media(BaseModel):
    markdown_content: str
    near_chunks: tuple[str, str]
    path: Optional[str] = None
    caption: Optional[str] = None

    @property
    def size(self):
        assert self.path is not None, "Path is required to get size"
        return Image.open(self.path).size

    def parse(self, image_dir: str):
        """
        Parse the markdown content to extract image path and alt text.
        Format expected: ![alt text](image.png)
        """
        match = IMAGE_PARSING_REGEX.search(self.markdown_content)
        if match is None:
            raise ValueError("No image found in the markdown content")
        image_path = match.group(1)
        if not pexists(image_path):
            image_path = pjoin(image_dir, image_path)
        assert pexists(image_path), f"image file not found: {image_path}"
        self.path = image_path

    async def get_caption(self, vision_model: AsyncLLM):
        assert self.path is not None, "Path is required to get caption"
        if self.caption is None:
            self.caption = await vision_model(
                IMAGE_CAPTION_PROMPT.render(
                    markdown_caption=self.near_chunks,
                ),
                self.path,
            )
            logger.debug(f"Caption: {self.caption}")


class Table(Media):
    cells: Optional[list[list[str]]] = None
    merge_area: Optional[list[tuple[int, int, int, int]]] = None

    def parse(self, image_dir: str):
        html = markdown(self.markdown_content)
        cells, merges = parse_table_with_merges(html)
        self.cells = cells
        self.merge_area = merges

        if self.path is None:
            self.path = pjoin(
                image_dir,
                f"table_{hashlib.md5(str(self.cells).encode()).hexdigest()[:4]}.png",
            )
        markdown_table_to_image(self.markdown_content, self.path)

    async def get_caption(self, language_model: AsyncLLM):
        if self.caption is None:
            self.caption = await language_model(
                TABLE_CAPTION_PROMPT.render(
                    markdown_content=self.markdown_content,
                    markdown_caption=self.near_chunks,
                )
            )
            logger.debug(f"Caption: {self.caption}")




class SubSection(BaseModel):
    title: str
    content: str


class Section(BaseModel):
    title: str
    summary: str
    blocks: list[SubSection | Media]
    markdown_content: Optional[str] = None

    @field_validator("blocks")
    def validate_blocks_not_empty(cls, v):
        if len(v) == 0:
            raise ValueError("blocks is empty")
        return v

    def iter_medias(self):
        for block in self.blocks:
            if isinstance(block, Media):
                yield block

    @classmethod
    def json_schema(cls):
        pydantic_schema = cls.model_json_schema()
        # Modify schema to only show SubSection in subsections, and add Metadata
        pydantic_schema["properties"]["blocks"]["items"] = {"$ref": "#/$defs/SubSection"}
        pydantic_schema["properties"]["metadata"] = {
            "additionalProperties": {"type": "string"},
            "title": "Metadata",
            "type": "object",
        }

        # Remove markdown_content from schema
        del pydantic_schema["$defs"]["Media"]
        del pydantic_schema["properties"]["markdown_content"]
        return pydantic_schema


def link_medias(
    medias: list[dict],
    section: Section,
    max_chunk_size: int = 256,
):
    """
    Link media elements to the section by inserting them into the blocks list at appropriate positions.

    Args:
        medias: List of media dictionaries (tables, images)
        section: Section object to insert medias into
        max_chunk_size: Maximum size of text chunk to consider for matching
    """
    if not medias:
        return

    # Convert media dictionaries to Media instances
    media_instances = []
    for media_dict in medias:
        if media_dict.get("type") == "table":
            media_instances.append(Table(**media_dict))
        else:
            media_instances.append(Media(**media_dict))

    # Find the best insertion position for each media
    for media in media_instances:
        if len(media.near_chunks[0]) < max_chunk_size:
            # If context is small, insert at the beginning
            section.blocks.insert(0, media)
        else:
            # Find the most similar SubSection based on content
            best_match_idx = 0
            best_similarity = 0

            for i, block in enumerate(section.blocks):
                if isinstance(block, SubSection):
                    similarity = edit_distance(media.near_chunks[0], block.content)
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_match_idx = i

            section.blocks.insert(best_match_idx + 1, media)
