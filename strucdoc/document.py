import asyncio
import contextlib
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from jinja2 import Environment, StrictUndefined

from .agent import Agent
from .doc_utils import (
    LogicHeadings,
    get_tree_structure,
    process_markdown_content,
    split_markdown_by_headings,
)
from .element import Section, SubSection, Table, link_medias
from .llms import AsyncLLM
from .utils import Language, get_logger, package_join, pbasename, pexists, pjoin

logger = get_logger(__name__)

env = Environment(undefined=StrictUndefined)

MERGE_METADATA_PROMPT = env.from_string(
    open(package_join("prompts", "merge_metadata.txt")).read()
)
HEADING_EXTRACT_PROMPT = env.from_string(
    open(package_join("prompts", "heading_extract.txt")).read()
)


@dataclass
class Document:
    image_dir: str
    sections: list[Section]
    metadata: dict[str, str]
    language: Language

    def __post_init__(self):
        self.metadata["presentation-date"] = datetime.now().strftime("%Y-%m-%d")
        assert pexists(
            self.image_dir
        ), f"image directory is not found: {self.image_dir}"
        for media in self.iter_medias():
            if pexists(media.path):
                continue
            basename = pbasename(media.path)
            if pexists(pjoin(self.image_dir, basename)):
                media.path = pjoin(self.image_dir, basename)
            else:
                raise FileNotFoundError(f"image file not found: {media.path}")

    def iter_medias(self):
        for section in self.blocks:
            yield from section.iter_medias()

    def get_table(self, image_path: str):
        for media in self.iter_medias():
            if media.path == image_path and isinstance(media, Table):
                return media
        raise ValueError(f"table not found: {image_path}")

    @classmethod
    async def _parse_chunk(
        cls,
        extractor: Agent,
        markdown_chunk: str,
        image_dir: str,
        language_model: AsyncLLM,
        vision_model: AsyncLLM,
        limiter: contextlib.AsyncExitStack,
    ):
        medias = process_markdown_content(
            markdown_chunk,
        )
        async with limiter:
            _, section = await extractor(
                markdown_document=markdown_chunk, response_format=Section.json_schema()
            )
            metadata = section.pop("metadata", {})
            section = Section(**section, markdown_content=markdown_chunk)
            link_medias(medias, section)
            for media in section.iter_medias():
                media.parse(image_dir)
                if isinstance(media, Table):
                    await media.get_caption(language_model)
                else:
                    await media.get_caption(vision_model)
        return metadata, section

    @classmethod
    async def from_markdown(
        cls,
        markdown_content: str,
        language_model: AsyncLLM,
        vision_model: AsyncLLM,
        image_dir: str,
        max_at_once: Optional[int] = None,
    ):
        doc_extractor = Agent(
            "doc_extractor",
            llm_mapping={"language": language_model, "vision": vision_model},
        )
        document_tree = get_tree_structure(markdown_content)
        headings = re.findall(r"^#+\s+.*", markdown_content, re.MULTILINE)
        adjusted_headings = await language_model(
            HEADING_EXTRACT_PROMPT.render(tree=document_tree),
            return_json=True,
            response_format=LogicHeadings.get_literal_schema(headings),
        )
        metadata = []
        sections = []
        tasks = []

        limiter = (
            asyncio.Semaphore(max_at_once)
            if max_at_once is not None
            else contextlib.AsyncExitStack()
        )
        async with asyncio.TaskGroup() as tg:
            for chunk in split_markdown_by_headings(
                markdown_content, headings, adjusted_headings["headings"]
            ):
                tasks.append(
                    tg.create_task(
                        cls._parse_chunk(
                            doc_extractor,
                            chunk,
                            image_dir,
                            language_model,
                            vision_model,
                            limiter,
                        )
                    )
                )

        # Process results in order
        for task in tasks:
            meta, section = task.result()
            metadata.append(meta)
            sections.append(section)

        merged_metadata = await language_model(
            MERGE_METADATA_PROMPT.render(metadata=metadata), return_json=True
        )
        return Document(
            image_dir=image_dir,
            metadata=merged_metadata,
            blocks=sections,
            language=Language.CJK,
        )

    def __contains__(self, key: str):
        for section in self.blocks:
            if section.title == key:
                return True
        return False

    def __getitem__(self, key: str):
        for section in self.blocks:
            if section.title == key:
                return section
        raise KeyError(
            f"section not found: {key}, available sections: {[section.title for section in self.blocks]}"
        )

    def retrieve(
        self,
        indexs: dict[str, list[str]],
    ) -> list[SubSection]:
        assert isinstance(
            indexs, dict
        ), "subsection_keys for index must be a dict, follow a two-level structure"
        subsecs = []
        for sec_key, subsec_keys in indexs.items():
            section = self[sec_key]
            for subsec_key in subsec_keys:
                subsecs.append(section[subsec_key])
        return subsecs

    def find_caption(self, caption: str):
        for media in self.iter_medias():
            if media.caption == caption:
                return media.path
        raise ValueError(f"Image caption not found: {caption}")

    def get_overview(self, include_summary: bool = False):
        overview = ""
        for section in self.blocks:
            overview += f"Section: {section.title}\n"
            if include_summary:
                overview += f"\tSummary: {section.summary}\n"
            for subsection in section.subsections:
                overview += f"\tSubsection: {subsection.title}\n"
                for media in subsection.medias:
                    overview += f"\t\tMedia: {media.caption}\n"
                overview += "\n"
        return overview

    @property
    def metainfo(self):
        return "\n".join([f"{k}: {v}" for k, v in self.metadata.items()])

    @property
    def dict(self):
        return {
            "metadata": self.metadata,
            "blocks": [section.model_dump(mode="json") for section in self.blocks],
            "language": self.language.value,
        }
