import logging
from dataclasses import dataclass
from typing import List, Optional
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
    def find_closest_duration(cls, quarter_length: float) -> DurationInfo:
        """
        根据 quarter_length 查找最接近的时值类型
        
        Args:
            quarter_length: 四分音符数量
            
        Returns:
            DurationInfo: 最接近的时值信息
        """
        all_durations = cls.BASE_DURATIONS + cls.DOTTED_DURATIONS
        closest = min(all_durations, 
                     key=lambda d: abs(d.quarter_length - quarter_length))
        
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
        """
        创建music21的Duration对象
        
        Args:
            duration_type: 时值类型名称（如果指定）
            dots: 附点数量（如果指定）
            quarter_length: 四分音符数量（如果指定）
            
        Returns:
            music21.duration.Duration对象
            
        Note:
            - 如果提供 quarter_length，将使用 find_closest_duration 查找最接近的时值
            - 如果提供 duration_type，将直接使用指定的时值类型
        """
        if quarter_length is not None:
            duration_info = cls.find_closest_duration(quarter_length)
            duration = music21.duration.Duration(type=duration_info.type_name)
            duration.dots = duration_info.dots
        else:
            if duration_type is None:
                raise ValueError("必须提供 duration_type 或 quarter_length")
            duration = music21.duration.Duration(type=duration_type)
            duration.dots = dots or 0
        
        logger.debug(
            f"创建Duration - 类型: {duration.type}, "
            f"附点: {duration.dots}, "
            f"四分音符数: {duration.quarterLength}"
        )
        
        return duration
    
    @classmethod
    def get_duration_info(cls, duration_type: str, dots: int = 0) -> DurationInfo:
        """
        获取指定时值类型的 DurationInfo
        
        Args:
            duration_type: 时值类型
            dots: 附点数量
            
        Returns:
            DurationInfo: 时值信息
        """
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