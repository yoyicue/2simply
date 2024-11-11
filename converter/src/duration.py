from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from enum import Enum, auto
import music21
from functools import lru_cache

class DotType(Enum):
    """附点类型"""
    NONE = auto()
    SINGLE = auto()
    DOUBLE = auto()

@dataclass(frozen=True)
class DurationInfo:
    """不可变的时值信息"""
    type_name: str
    quarter_length: float
    beats: float
    description: str
    is_dotted: bool = False

class DurationManager:
    """时值管理的核心逻辑"""
    BASE_DURATIONS: Dict[str, DurationInfo] = {
        "whole": DurationInfo("whole", 4.0, 4.0, "全音符"),
        "half": DurationInfo("half", 2.0, 2.0, "二分音符"),
        "quarter": DurationInfo("quarter", 1.0, 1.0, "四分音符"),
        "eighth": DurationInfo("eighth", 0.5, 0.5, "八分音符"),
        "16th": DurationInfo("16th", 0.25, 0.25, "十六分音符"),
    }

    DOTTED_DURATIONS: Dict[str, DurationInfo] = {
        "dotted-half": DurationInfo("half", 3.0, 3.0, "附点二分音符", True),
        "dotted-quarter": DurationInfo("quarter", 1.5, 1.5, "附点四分音符", True),
    }

    @classmethod
    @lru_cache(maxsize=128)
    def find_closest_duration(cls, quarter_length: float) -> DurationInfo:
        """高效查找最接近的时值"""
        all_durations = {**cls.BASE_DURATIONS, **cls.DOTTED_DURATIONS}
        return min(
            all_durations.values(), 
            key=lambda d: abs(d.quarter_length - quarter_length)
        )

    @classmethod
    def create_music21_duration(cls, quarter_length: float) -> music21.duration.Duration:
        """创建标准music21时值对象"""
        duration_info = cls.find_closest_duration(quarter_length)
        duration = music21.duration.Duration(quarterLength=duration_info.quarter_length)
        duration.dots = 1 if duration_info.is_dotted else 0
        return duration

    @classmethod
    def validate_measure_duration(
        cls, 
        elements: List[music21.base.Music21Object], 
        expected_length: float = 4.0
    ) -> Tuple[bool, float]:
        """验证小节总时值"""
        total_length = sum(elem.duration.quarterLength for elem in elements)
        return abs(total_length - expected_length) < 0.001, total_length