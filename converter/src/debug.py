# src/debug.py
from typing import List, Union, Dict, Optional
from dataclasses import dataclass
from src.constants import (
    Note, ClefType, Measure,
    STAFF_SPLIT_Y, BEATS_PER_MEASURE
)
from src.duration import DurationManager, DurationInfo
import music21

@dataclass
class StaffDebugInfo:
    """谱表调试信息"""
    notes: List[Note]
    processed_elements: List[Union[music21.note.Note, music21.note.Rest, music21.chord.Chord]]
    staff_type: ClefType
    
    def print_info(self, indent: str = "  "):
        """打印谱表信息"""
        print(f"{indent}原始音符:")
        if not self.notes:
            print(f"{indent * 2}整小节休止符")
        else:
            for note in sorted(self.notes, key=lambda n: n.position_beats):
                print(f"{indent * 2}{note.pitch_name} @ 位置{note.position_beats}拍, "
                      f"持续{note.duration_beats}拍")
        
        print(f"{indent}处理后:")
        if not self.processed_elements:
            print(f"{indent * 2}整小节休止符")
        else:
            for elem in self.processed_elements:
                self._print_element(elem, indent * 2)
    
    def _print_element(self, element: Union[music21.note.Note, music21.note.Rest, music21.chord.Chord], 
                      indent: str):
        """打印音乐元素"""
        duration_info = DurationManager.find_closest_duration(element.duration.quarterLength)
        
        if isinstance(element, music21.note.Note):
            print(f"{indent}音符: {element.nameWithOctave} ({duration_info.description})")
        elif isinstance(element, music21.note.Rest):
            print(f"{indent}休止符: {duration_info.description}")
        elif isinstance(element, music21.chord.Chord):
            notes_str = ", ".join(n.nameWithOctave for n in element.notes)
            print(f"{indent}和弦: [{notes_str}] ({duration_info.description})")

@dataclass
class MeasureDebugInfo:
    """小节调试信息"""
    measure_number: int
    original_notes: List[Note]
    processed_measure: music21.stream.Measure
    _treble_info: Optional[StaffDebugInfo] = None
    _bass_info: Optional[StaffDebugInfo] = None
    
    def __post_init__(self):
        """初始化后处理"""
        self._init_staff_info()
    
    def _init_staff_info(self):
        """初始化谱表信息"""
        # 分离原始音符
        treble_notes = [n for n in self.original_notes if n.y >= STAFF_SPLIT_Y]
        bass_notes = [n for n in self.original_notes if n.y < STAFF_SPLIT_Y]
        
        # 获取处理后的音符
        parts = [p for p in self.processed_measure.elements if isinstance(p, music21.stream.Part)]
        if len(parts) >= 2:
            treble_elements = list(parts[0].recurse().getElementsByClass(
                ['Note', 'Rest', 'Chord']))
            bass_elements = list(parts[1].recurse().getElementsByClass(
                ['Note', 'Rest', 'Chord']))
            
            self._treble_info = StaffDebugInfo(
                notes=treble_notes,
                processed_elements=treble_elements,
                staff_type=ClefType.TREBLE
            )
            self._bass_info = StaffDebugInfo(
                notes=bass_notes,
                processed_elements=bass_elements,
                staff_type=ClefType.BASS
            )
    
    def print_comparison(self):
        """打印比较信息"""
        print(f"\n=== 小节 {self.measure_number} ===")
        
        # 分别计算高音谱和低音谱的时值
        treble_length = 0.0
        bass_length = 0.0
        
        if self._treble_info:
            treble_length = sum(elem.duration.quarterLength 
                              for elem in self._treble_info.processed_elements)
        
        if self._bass_info:
            bass_length = sum(elem.duration.quarterLength 
                            for elem in self._bass_info.processed_elements)
        
        # 使用较大的时值作为小节时值（因为两个谱表是并行的）
        total_length = max(treble_length, bass_length)
        is_valid = abs(total_length - BEATS_PER_MEASURE) < 0.001
        
        print(f"小节时值: {total_length}拍 ({'正确' if is_valid else '错误'})")
        
        # 打印高音谱表信息
        print("\n高音谱表:")
        if self._treble_info:
            self._treble_info.print_info()
        else:
            print("  未找到高音谱表信息")
        
        # 打印低音谱表信息
        print("\n低音谱表:")
        if self._bass_info:
            self._bass_info.print_info()
        else:
            print("  未找到低音谱表信息")

class ScoreDebugger:
    """乐谱调试器"""
    def __init__(self, debug_measures: Optional[List[int]] = None):
        self.debug_measures = set(debug_measures or [])  # 使用set提高查找效率
        self.measure_info = {}  # 存储小节信息
    
    def should_debug(self, measure_number: int) -> bool:
        """检查是否需要调试该小节"""
        return not self.debug_measures or measure_number in self.debug_measures
    
    def compare_measure(self, measure_number: int, json_measure: Measure, m21_measure: music21.stream.Measure):
        """比较JSON和music21的小节"""
        if not self.should_debug(measure_number):
            return
            
        # 创建小节调试信息
        debug_info = MeasureDebugInfo(
            measure_number=measure_number,
            original_notes=json_measure.notes,
            processed_measure=m21_measure
        )
        
        # 存储调试信息
        self.measure_info[measure_number] = debug_info
        
        # 打印比较信息
        debug_info.print_comparison()
    
    def print_summary(self):
        """打印调试信息汇总"""
        if not self.measure_info:
            return
            
        print("\n=== 调试信息汇总 ===")
        for measure_number in sorted(self.debug_measures):
            if measure_number not in self.measure_info:
                print(f"小节 {measure_number} 未找到")
                continue
                
            info = self.measure_info[measure_number]
            print(f"\n小节 {measure_number} 验证:")
            
            # 验证音符分配
            if info._treble_info:
                print("  高音谱表:")
                print(f"    原始音符数: {len(info._treble_info.notes)}")
                print(f"    处理后音符数: {len(info._treble_info.processed_elements)}")
                
            if info._bass_info:
                print("  低音谱表:")
                print(f"    原始音符数: {len(info._bass_info.notes)}")
                print(f"    处理后音符数: {len(info._bass_info.processed_elements)}")
            
            # 分别计算高音谱和低音谱的时值
            treble_length = 0.0
            bass_length = 0.0
            
            if info._treble_info:
                treble_length = sum(elem.duration.quarterLength 
                                  for elem in info._treble_info.processed_elements)
            
            if info._bass_info:
                bass_length = sum(elem.duration.quarterLength 
                                for elem in info._bass_info.processed_elements)
            
            # 使用较大的时值作为小节时值
            total_length = max(treble_length, bass_length)
            is_valid = abs(total_length - BEATS_PER_MEASURE) < 0.001
            
            print(f"  时值验证: {'✓' if is_valid else '✗'} ({total_length}拍)")
