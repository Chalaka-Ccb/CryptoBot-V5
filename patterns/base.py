# patterns/base.py

from abc import ABC, abstractmethod
from core.models.candle import Candle
from core.models.pattern import PatternResult
from patterns.config import PatternConfig


class BasePattern(ABC):

    name: str

    def __init__(self, config: PatternConfig | None = None):
        self.config = config or PatternConfig()

    @abstractmethod
    def detect(self, candles: list[Candle]) -> PatternResult:
        pass