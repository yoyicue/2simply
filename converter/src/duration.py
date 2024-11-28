import logging
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple, Union
import music21

logger = logging.getLogger(__name__)

@dataclass
class DurationInfo:
    type_name: str
    quarter_length: float
    is_dotted: bool = False
    dots: int = 0
    default_width: float = 30.0
    dot_width_increment: float = 5.0

class DurationManager:
    """统一的时值管理器 - 支持双向转换"""
    
    # 添加类变量来存储调试信息
    debug_measures: Set[int] = set()
    current_measure: int = 0
    debug_enabled: bool = False  # 添加调试开关
    
    # 增加容差值
    TOLERANCE = 0.05
    
    # 基本时值定义
    BASE_DURATIONS = [
        DurationInfo(type_name='whole', quarter_length=4.0),
        DurationInfo(type_name='half', quarter_length=2.0),
        DurationInfo(type_name='quarter', quarter_length=1.0),
        DurationInfo(type_name='eighth', quarter_length=0.5),
        DurationInfo(type_name='16th', quarter_length=0.25),
        DurationInfo(type_name='32nd', quarter_length=0.125),
        DurationInfo(type_name='64th', quarter_length=0.0625)
    ]
    
    # 附点时值定义
    DOTTED_DURATIONS = [
        DurationInfo(type_name=d.type_name, quarter_length=d.quarter_length * 1.5,
                    is_dotted=True, dots=1)
        for d in BASE_DURATIONS
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
        """查找最接近的时值，优先考虑标准时值"""
        # 特殊处理四分音符的情况（处理0.167这种情况）
        if 0.15 <= quarter_length <= 0.18:  # 针对0.167的情况
            return next(d for d in cls.BASE_DURATIONS if d.type_name == 'quarter')

        # 首先检查是否接近标准时值
        for duration in cls.BASE_DURATIONS:
            if abs(duration.quarter_length - quarter_length) <= cls.TOLERANCE:
                if cls.should_log():
                    logger.debug(
                        f"查找时值 - 目标: {quarter_length}, "
                        f"匹配标准时值: {duration.type_name} "
                        f"(时值: {duration.quarter_length})"
                    )
                return duration

        # 如果没有匹配的标准时值，再查找包括附点时值在内的最接近值
        all_durations = cls.BASE_DURATIONS + cls.DOTTED_DURATIONS
        closest = min(all_durations,
                     key=lambda d: abs(d.quarter_length - quarter_length))

        if cls.should_log():
            logger.debug(
                f"查找时值 - 目标: {quarter_length}, "
                f"最接近的时值: {closest.type_name} "
                f"(时值: {closest.quarter_length}, 附点: {closest.is_dotted})"
            )

        return closest
    
    @classmethod
    def create_duration(
        cls,
        duration_type: Optional[str] = None,
        quarter_length: Optional[float] = None,
        dots: int = 0
    ) -> music21.duration.Duration:
        """创建music21 Duration对象"""
        if duration_type is not None:
            duration = music21.duration.Duration(type=duration_type)
            duration.dots = dots
            return duration

        if quarter_length is not None:
            dur_info = cls.find_closest_duration(quarter_length)
            duration = music21.duration.Duration(type=dur_info.type_name)
            duration.dots = dur_info.dots
            return duration

        raise ValueError("必须提供duration_type或quarter_length参数")
    
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
    
    @classmethod
    def from_music21_duration(cls, duration: music21.duration.Duration) -> DurationInfo:
        """从music21 Duration对象提取时值信息"""
        quarter_length = duration.quarterLength
        dots = duration.dots
        
        # 首先尝试精确匹配
        all_durations = cls.BASE_DURATIONS + cls.DOTTED_DURATIONS
        for dur_info in all_durations:
            if (dur_info.quarter_length == quarter_length and 
                dur_info.dots == dots):
                return dur_info
        
        # 如果没有精确匹配，查找最接近的标准时值
        closest = cls.find_closest_duration(quarter_length)
        
        if cls.should_log():
            logger.debug(
                f"从music21提取时值 - 原始: {duration.type}({duration.quarterLength}), "
                f"转换后: {closest.type_name}({closest.quarter_length})"
            )
        
        return closest
    
    @classmethod
    def extract_duration_info(
        cls,
        element: Union[music21.note.Note, music21.note.Rest, music21.chord.Chord]
    ) -> Tuple[DurationInfo, float, float]:
        """从music21音乐元素提取完整的时值信息
        
        Args:
            element: music21音乐元素（音符、休止符或和弦）
            
        Returns:
            Tuple[DurationInfo, float, float]: 返回(时值信息, 拍数, 秒数)
        """
        duration = element.duration
        dur_info = cls.from_music21_duration(duration)
        
        # 计算精确的时间长度
        beats = duration.quarterLength / 4.0  # 将四分音符长度转换为以全音符为单位
        seconds = duration.quarterLength * 60 / cls._get_tempo(element)  # 使用原始的quarterLength计算秒数
        
        # 检查是否为连音符组的一部分
        if hasattr(duration, 'tuplets') and duration.tuplets:
            tuplet = duration.tuplets[0]  # 获取第一个连音符信息
            actual = tuplet.numberNotesActual
            normal = tuplet.numberNotesNormal
            # 调整连音符的持续时间
            beats = beats * normal / actual
            seconds = seconds * normal / actual
        
        if cls.should_log():
            logger.debug(
                f"提取时值信息 - 类型: {dur_info.type_name}, "
                f"拍数: {beats}, 秒数: {seconds:.3f}"
            )
        
        return dur_info, beats, seconds
    
    @classmethod
    def _get_tempo(cls, element: music21.base.Music21Object) -> float:
        """获取音符所在位置的速度"""
        # 查找最近的速度标记
        tempo = element.getContextByClass(music21.tempo.MetronomeMark)
        if tempo:
            return tempo.number
        return 120.0  # 默认速度
    
    @classmethod
    def validate_duration(
        cls,
        duration_type: str,
        quarter_length: float,
        dots: int = 0
    ) -> bool:
        """验证时值信息的一致性"""
        dur_info = cls.get_duration_info(duration_type, dots)
        return abs(dur_info.quarter_length - quarter_length) < 0.001
    
    @classmethod
    def get_duration_components(
        cls,
        quarter_length: float
    ) -> Tuple[str, int]:
        """获取时值的组成部分（基本时值类型和附点数）"""
        dur_info = cls.find_closest_duration(quarter_length)
        return dur_info.type_name, dur_info.dots
    
    @classmethod
    def create_duration_from_info(cls, dur_info: DurationInfo) -> music21.duration.Duration:
        """从DurationInfo创建music21 Duration对象"""
        duration = music21.duration.Duration(type=dur_info.type_name)
        duration.dots = dur_info.dots
        return duration
    
    @classmethod
    def calculate_width(cls, dur_info: DurationInfo) -> float:
        """计算音符实际宽度（考虑附点）"""
        width = dur_info.default_width
        if dur_info.dots > 0:
            width += dur_info.dots * dur_info.dot_width_increment
        return width
    
    @classmethod
    def decompose_duration(cls, quarter_length: float) -> List[DurationInfo]:
        """将给定的时值分解为标准时值组合
        
        Args:
            quarter_length: 要分解的时值（以四分音符为单位）
            
        Returns:
            List[DurationInfo]: 标准时值组合列表
            
        Examples:
            1.5 -> [四分音符(1.0), 八分音符(0.5)]
            2.5 -> [二分音符(2.0), 八分音符(0.5)]
            3.5 -> [二分音符(2.0), 四分音符(1.0), 八分音符(0.5)]
        """
        result = []
        remaining = quarter_length
        
        # 优先使用基本时值，按照时值从大到小排序
        base_durations = sorted(
            cls.BASE_DURATIONS,
            key=lambda x: x.quarter_length,
            reverse=True
        )
        
        # 如果剩余时值完全匹配某个基本时值，直接返回
        for duration in base_durations:
            if abs(duration.quarter_length - quarter_length) < 0.001:
                return [duration]
        
        # 如果没有完全匹配的基本时值，检查是否匹配带附点的时值
        dotted_durations = sorted(
            cls.DOTTED_DURATIONS,
            key=lambda x: x.quarter_length,
            reverse=True
        )
        
        for duration in dotted_durations:
            if abs(duration.quarter_length - quarter_length) < 0.001:
                # 对于带附点的时值，将其分解为基本时值
                # 例如：附点四分音符(1.5) -> 四分音符(1.0) + 八分音符(0.5)
                base_type = duration.type_name
                base_duration = next(d for d in base_durations if d.type_name == base_type)
                remaining_duration = duration.quarter_length - base_duration.quarter_length
                
                result.append(base_duration)
                if remaining_duration > 0:
                    # 递归处理剩余时值
                    result.extend(cls.decompose_duration(remaining_duration))
                return result
        
        # 如果没有完全匹配，则使用基本时值进行分解
        while remaining > 0:
            # 找到不超过剩余时值的最大基本时值
            found = False
            for duration in base_durations:
                if duration.quarter_length <= remaining + 0.001:  # 添加小误差容忍
                    result.append(duration)
                    remaining -= duration.quarter_length
                    found = True
                    break
            
            if not found:
                # 如果找不到合适的时值，使用最小的时值（通常是32分音符）
                smallest = min(base_durations, key=lambda x: x.quarter_length)
                result.append(smallest)
                remaining -= smallest.quarter_length
        
        if cls.should_log():
            logger.debug(
                f"分解时值 {quarter_length} -> " +
                ", ".join([f"{d.type_name}({d.quarter_length})" for d in result])
            )
        
        return result
    
    @classmethod
    def create_rest_with_duration(cls, quarter_length: float) -> List[music21.note.Rest]:
        """创建一组标准时值的休止符
        
        Args:
            quarter_length: 总时值（以四分音符为单位）
            
        Returns:
            List[music21.note.Rest]: 休止符列表
        """
        durations = cls.decompose_duration(quarter_length)
        rests = []
        
        for dur_info in durations:
            rest = music21.note.Rest()
            rest.duration = cls.create_duration_from_info(dur_info)
            rests.append(rest)
        
        if cls.should_log():
            logger.debug(
                f"创建休止符组 {quarter_length} -> " +
                ", ".join([f"{r.duration.type}({r.duration.quarterLength})" for r in rests])
            )
        
        return rests