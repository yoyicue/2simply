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
    
    def compare_measure(
        self, 
        measure_number: int, 
        measure_data: 'Measure', 
        treble_measure: music21.stream.Measure, 
        bass_measure: music21.stream.Measure
    ):
        """比较处理前后的小节，确保转换正确"""
        print(f"\nDebug: Comparing Measure {measure_number}")
        
        # 获取原始和转换后的高音谱表音符
        original_treble_notes = measure_data.get_notes_by_staff(ClefType.TREBLE)
        converted_treble_notes = [n for n in treble_measure.notes if isinstance(n, music21.note.Note)]
        
        # 获取原始和转换后的低音谱表音符
        original_bass_notes = measure_data.get_notes_by_staff(ClefType.BASS)
        converted_bass_notes = [n for n in bass_measure.notes if isinstance(n, music21.note.Note)]
        
        # 解析音符为 music21.Pitch 对象
        original_treble_pitches = [music21.pitch.Pitch(n.pitchName) for n in original_treble_notes]
        converted_treble_pitches = [music21.pitch.Pitch(n.nameWithOctave) for n in converted_treble_notes]
        
        original_bass_pitches = [music21.pitch.Pitch(n.pitchName) for n in original_bass_notes]
        converted_bass_pitches = [music21.pitch.Pitch(n.nameWithOctave) for n in converted_bass_notes]
        
        # 打印原始和转换后的音符
        print(f"  Original Treble Notes: {[p.nameWithOctave for p in original_treble_pitches]}")
        print(f"  Converted Treble Notes: {[f'{p.nameWithOctave} ({n.duration.type}{'+' if n.duration.dots else ''})' for p, n in zip(converted_treble_pitches, converted_treble_notes)]}")
        
        print(f"  Original Bass Notes: {[p.nameWithOctave for p in original_bass_pitches]}")
        print(f"  Converted Bass Notes: {[f'{p.nameWithOctave} ({n.duration.type}{'+' if n.duration.dots else ''})' for p, n in zip(converted_bass_pitches, converted_bass_notes)]}")
        
        # 比较音符数量
        treble_count = len(original_treble_pitches)
        treble_converted_count = len(converted_treble_pitches)
    
        if treble_count != treble_converted_count:
            print(f"  Error: Treble notes count mismatch. Original: {treble_count}, Converted: {treble_converted_count}")
        else:
            print(f"  Measure {measure_number} Treble notes count match.")
    
        bass_count = len(original_bass_pitches)
        bass_converted_count = len(converted_bass_pitches)
    
        if bass_count != bass_converted_count:
            print(f"  Error: Bass notes count mismatch. Original: {bass_count}, Converted: {bass_converted_count}")
        else:
            print(f"  Measure {measure_number} Bass notes count match.")
        
        # 进一步比较每个音符的音高和时值
        for i, (orig_p, conv_p, conv_n) in enumerate(zip(original_treble_pitches, converted_treble_pitches, converted_treble_notes)):
            if orig_p.midi != conv_p.midi:
                print(f"    Error: Treble Note {i+1} pitch mismatch. Original: {orig_p.nameWithOctave}, Converted: {conv_p.nameWithOctave}")
            if round(measure_data.notes[i].durationBeats, 2) != round(conv_n.duration.quarterLength, 2):
                print(f"    Error: Treble Note {i+1} duration mismatch. Original: {measure_data.notes[i].durationBeats}, Converted: {conv_n.duration.quarterLength}")
        
        for i, (orig_p, conv_p, conv_n) in enumerate(zip(original_bass_pitches, converted_bass_pitches, converted_bass_notes)):
            if orig_p.midi != conv_p.midi:
                print(f"    Error: Bass Note {i+1} pitch mismatch. Original: {orig_p.nameWithOctave}, Converted: {conv_p.nameWithOctave}")
            if round(measure_data.notes[i].durationBeats, 2) != round(conv_n.duration.quarterLength, 2):
                print(f"    Error: Bass Note {i+1} duration mismatch. Original: {measure_data.notes[i].durationBeats}, Converted: {conv_n.duration.quarterLength}")

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
