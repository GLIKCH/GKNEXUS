from dataclasses import dataclass
from typing import List, Dict

@dataclass
class Conversation:
    id: str
    metadata: Dict
    messages: List[Dict]
