from typing import List, Literal

from pydantic import BaseModel


class CharacterDescription(BaseModel):
    name: str
    type: Literal["speaking", "creature", "npc_entity"]
    importance: Literal["major", "minor"]
    description: str
    base_name: str = ""
    version_label: str = "default"
    version_index: int = 0
    appears_from: str = ""
    identity_anchor: str = ""


class CharacterList(BaseModel):
    characters: List[CharacterDescription]


class CharacterPrompts(BaseModel):
    name: str
    front_profile_prompt: str
    turnaround_prompt: str


class CharacterPromptsList(BaseModel):
    characters: List[CharacterPrompts]


class FrontProfilePrompt(BaseModel):
    name: str
    front_profile_prompt: str


class FrontProfilePromptList(BaseModel):
    characters: List[FrontProfilePrompt]


class TurnaroundPrompt(BaseModel):
    name: str
    turnaround_prompt: str


class TurnaroundPromptList(BaseModel):
    characters: List[TurnaroundPrompt]
