from dataclasses import dataclass
from typing import List
import music21

@dataclass
class DurationInfo:
    type_name: str
    quarter_length: float
    is_dotted: bool

class DurationManager:
    @staticmethod
    def find_closest_duration(quarter_length: float) -> DurationInfo:
        """根据 quarter_length 查找最接近的时值类型"""
        # 定义可用的基础时值
        base_durations = [
            DurationInfo(type_name='whole', quarter_length=4.0, is_dotted=False),
            DurationInfo(type_name='half', quarter_length=2.0, is_dotted=False),
            DurationInfo(type_name='quarter', quarter_length=1.0, is_dotted=False),
            DurationInfo(type_name='eighth', quarter_length=0.5, is_dotted=False),
            DurationInfo(type_name='16th', quarter_length=0.25, is_dotted=False),
        ]
        
        # 定义附点时值
        dotted_durations = [
            DurationInfo(type_name='half', quarter_length=3.0, is_dotted=True),
            DurationInfo(type_name='quarter', quarter_length=1.5, is_dotted=True),
            DurationInfo(type_name='eighth', quarter_length=0.75, is_dotted=True),
        ]
        
        all_durations = base_durations + dotted_durations
        
        # 找出最接近的时值
        closest = min(all_durations, key=lambda d: abs(d.quarter_length - quarter_length))
        return closest
    
    @classmethod
    def create_music21_duration(cls, quarter_length: float) -> music21.duration.Duration:
        """创建标准music21时值对象"""
        duration_info = cls.find_closest_duration(quarter_length)
        duration = music21.duration.Duration()
        
        # 设置类型和附点
        duration.type = duration_info.type_name
        duration.dots = 1 if duration_info.is_dotted else 0
        
        # 输出调试信息
        print(f"Debug: Created Duration - Type: {duration.type}, Dots: {duration.dots}, Expected quarterLength: {duration_info.quarter_length}, Actual quarterLength: {duration.quarterLength}")
        
        return duration