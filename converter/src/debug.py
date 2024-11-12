# src/debug.py
import logging
from dataclasses import dataclass
from typing import List, Union, Dict, Optional
import music21
from src.constants import (
    Note, ClefType, Measure,
    STAFF_SPLIT_Y, BEATS_PER_MEASURE
)

logger = logging.getLogger(__name__)

@dataclass
class StaffDebugInfo:
    """谱表调试信息"""
    notes: List[Note]
    processed_elements: List[Union[music21.note.Note, music21.note.Rest, music21.chord.Chord]]
    staff_type: ClefType
    
    def print_info(self, indent: str = "  "):
        """打印谱表信息"""
        if not self.notes:
            logger.debug(f"{indent}原始音符: 整小节休止符")
        else:
            logger.debug(f"{indent}原始音符:")
            for note in sorted(self.notes, key=lambda n: n.position_beats):
                logger.debug(
                    f"{indent * 2}{note.pitch_name} @ "
                    f"位置{note.position_beats}拍, "
                    f"持续{note.durationBeats}拍 "
                    f"({note.durationType}{'+' * note.dots})"
                )
        
        if not self.processed_elements:
            logger.debug(f"{indent}处理后: 整小节休止符")
        else:
            logger.debug(f"{indent}处理后:")
            for elem in self.processed_elements:
                self._print_element(elem, indent * 2)
    
    def _print_element(
        self,
        element: Union[music21.note.Note, music21.note.Rest, music21.chord.Chord],
        indent: str
    ):
        """打印音乐元素"""
        duration_desc = f"{element.duration.type}{'+' * element.duration.dots}"
        
        if isinstance(element, music21.note.Note):
            logger.debug(f"{indent}音符: {element.nameWithOctave} ({duration_desc})")
        elif isinstance(element, music21.note.Rest):
            logger.debug(f"{indent}休止符: ({duration_desc})")
        elif isinstance(element, music21.chord.Chord):
            notes_str = ", ".join(n.nameWithOctave for n in element.notes)
            logger.debug(f"{indent}和弦: [{notes_str}] ({duration_desc})")

class ScoreDebugger:
    """乐谱调试器"""
    
    def __init__(self, measure_numbers: Optional[List[int]] = None):
        """
        初始化调试器
        :param measure_numbers: 需要调试的小节号列表
        """
        self.measure_numbers = measure_numbers or []
    
    def should_debug(self, measure_number: int) -> bool:
        """判断是否需要调试该小节"""
        return measure_number in self.measure_numbers
    
    def validate_measure(self, measure_info: StaffDebugInfo) -> bool:
        """验证小节的时值总和是否正确"""
        total_length = sum(
            elem.duration.quarterLength 
            for elem in measure_info.processed_elements
        )
        return abs(total_length - BEATS_PER_MEASURE) < 0.001
    
    def compare_measure(self, measure_number: int, measure_data, treble_measure, bass_measure):
        """Compare the original measure data with the converted measures"""
        if measure_number not in self.measure_numbers:
            return
            
        # 避免重复处理同一小节
        if measure_number in self._processed_measures:
            return
            
        self._processed_measures.add(measure_number)
        self.measure_info[measure_number] = {
            'treble': treble_measure,
            'bass': bass_measure,
            'original': measure_data
        }
            
        print(f"\n=== Debugging Measure {measure_number} ===")
        print("Original Measure Data:")
        print(f"Start Position: {measure_data.start_position_beats}")
        
        # 打印原始JSON中的音符信息
        if hasattr(measure_data, 'notes'):
            print("\nOriginal Notes:")
            for note in measure_data.notes:
                print(f"Note: {note.pitch_name} @ position {note.position_beats}, "
                      f"duration {note.duration_beats} beats")
        
        print("\nConverted Result:")
        print("Treble Staff:")
        self._print_staff_elements(treble_measure.elements)
                
        print("\nBass Staff:")
        self._print_staff_elements(bass_measure.elements)
    
    def _print_staff_elements(self, elements):
        """Helper method to print staff elements"""
        for element in elements:
            if isinstance(element, music21.note.Note):
                print(f"Note: {element.nameWithOctave}, Duration: {element.duration.quarterLength}")
            elif isinstance(element, music21.note.Rest):
                print(f"Rest: Duration: {element.duration.quarterLength}")
            elif isinstance(element, music21.chord.Chord):
                notes = [n.nameWithOctave for n in element.notes]
                print(f"Chord: {notes}, Duration: {element.duration.quarterLength}")