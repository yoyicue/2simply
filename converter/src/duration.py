import logging
from dataclasses import dataclass
from typing import List, Optional, Set
import music21

logger = logging.getLogger(__name__)

@dataclass
class DurationInfo:
    type_name: str
    quarter_length: float
    is_dotted: bool = False
    dots: int = 0

class DurationManager:
    """时值管理器"""
    
    # 添加类变量来存储调试信息
    debug_measures: Set[int] = set()
    current_measure: int = 0
    debug_enabled: bool = False  # 添加调试开关
    
    # 定义基础时值映射
    BASE_DURATIONS = [
        DurationInfo(type_name='whole', quarter_length=4.0),
        DurationInfo(type_name='half', quarter_length=2.0),
        DurationInfo(type_name='quarter', quarter_length=1.0),
        DurationInfo(type_name='eighth', quarter_length=0.5),
        DurationInfo(type_name='16th', quarter_length=0.25),
        DurationInfo(type_name='32nd', quarter_length=0.125)
    ]
    
    # 定义附点时值
    DOTTED_DURATIONS = [
        DurationInfo(type_name='half', quarter_length=3.0, is_dotted=True, dots=1),
        DurationInfo(type_name='quarter', quarter_length=1.5, is_dotted=True, dots=1),
        DurationInfo(type_name='eighth', quarter_length=0.75, is_dotted=True, dots=1),
        # 双附点时值
        DurationInfo(type_name='half', quarter_length=3.5, is_dotted=True, dots=2),
        DurationInfo(type_name='quarter', quarter_length=1.75, is_dotted=True, dots=2),
        DurationInfo(type_name='eighth', quarter_length=0.875, is_dotted=True, dots=2),
    ]
    
    @classmethod
    def set_debug_info(cls, debug_measures: List[int], current_measure: int, debug_enabled: bool = False) -> None:
        """设置调试信息"""
        cls.debug_measures = set(debug_measures) if debug_measures else set()
        cls.current_measure = current_measure
        cls.debug_enabled = debug_enabled
    
    @classmethod
    def should_log(cls) -> bool:
        """判断是否应该输出日志"""
        return (cls.debug_enabled and  # 首先检查是否启用调试
                (not cls.debug_measures or cls.current_measure in cls.debug_measures))
    
    @classmethod
    def find_closest_duration(cls, quarter_length: float) -> DurationInfo:
        """根据 quarter_length 查找最接近的时值类型"""
        all_durations = cls.BASE_DURATIONS + cls.DOTTED_DURATIONS
        closest = min(all_durations, 
                     key=lambda d: abs(d.quarter_length - quarter_length))
        
        if cls.should_log():
            logger.debug(
                f"查找时值 - 目标: {quarter_length}, "
                f"找到: {closest.type_name} "
                f"(附点: {closest.dots}, "
                f"时值: {closest.quarter_length})"
            )
        
        return closest
    
    @classmethod
    def create_duration(
        cls,
        duration_type: Optional[str] = None,
        dots: Optional[int] = None,
        quarter_length: Optional[float] = None
    ) -> music21.duration.Duration:
        """创建music21的Duration对象"""
        if quarter_length is not None:
            duration_info = cls.find_closest_duration(quarter_length)
            duration = music21.duration.Duration(type=duration_info.type_name)
            duration.dots = duration_info.dots
        else:
            if duration_type is None:
                raise ValueError("必须提供 duration_type 或 quarter_length")
            duration = music21.duration.Duration(type=duration_type)
            duration.dots = dots or 0
        
        if cls.should_log():
            logger.debug(
                f"创建Duration - 类型: {duration.type}, "
                f"附点: {duration.dots}, "
                f"四分音符数: {duration.quarterLength}"
            )
        
        return duration
    
    @classmethod
    def get_duration_info(cls, duration_type: str, dots: int = 0) -> DurationInfo:
        """获取指定时值类型的 DurationInfo"""
        all_durations = cls.BASE_DURATIONS + cls.DOTTED_DURATIONS
        for duration in all_durations:
            if duration.type_name == duration_type and duration.dots == dots:
                return duration
        
        # 如果找不到匹配的预定义时值，创建一个新的
        duration = music21.duration.Duration(type=duration_type)
        duration.dots = dots
        return DurationInfo(
            type_name=duration_type,
            quarter_length=duration.quarterLength,
            is_dotted=dots > 0,
            dots=dots
        )