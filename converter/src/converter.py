# src/converter.py
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
import music21
from src.constants import (
    Note, Score, ClefType, NoteType, Measure, Position,
    STAFF_SPLIT_Y,BEATS_PER_MEASURE,
    TIME_SIGNATURE, KEY_SIGNATURE
)
from src.duration import DurationManager
from src.debug import ScoreDebugger
import copy

class ScoreConverter:
    """乐谱转换器"""
    
    def __init__(self, score_data: Score, debugger: Optional[ScoreDebugger] = None):
        self.score_data = score_data
        self.debugger = debugger
    
    def convert(self) -> music21.stream.Score:
        """将JSON格式的乐谱转换为music21格式"""
        score = music21.stream.Score()
        
        # 创建高音谱表和低音谱表
        treble_part = music21.stream.Part()
        bass_part = music21.stream.Part()
        
        # 添加谱号
        treble_part.append(music21.clef.TrebleClef())
        bass_part.append(music21.clef.BassClef())
        
        # 添加调号
        treble_part.append(music21.key.Key(KEY_SIGNATURE))
        bass_part.append(music21.key.Key(KEY_SIGNATURE))
        
        # 添加拍号
        treble_part.append(music21.meter.TimeSignature(TIME_SIGNATURE))
        bass_part.append(music21.meter.TimeSignature(TIME_SIGNATURE))
        
        # 处理每个小节
        for measure in self.score_data.measures:
            m21_measure = self._process_measure(measure.number, measure)
            treble_part.append(m21_measure)
            bass_part.append(m21_measure)
        
        # 将声部添加到乐谱
        score.append(treble_part)
        score.append(bass_part)
        
        return score
    
    def _process_measure(self, measure_number: int, measure_data: Measure) -> music21.stream.Measure:
        """处理单个小节，确保严格遵守4/4拍"""
        measure = music21.stream.Measure(number=measure_number)
        measure.timeSignature = music21.meter.TimeSignature(TIME_SIGNATURE)
        
        for clef_type in [ClefType.TREBLE, ClefType.BASS]:
            staff = music21.stream.PartStaff()
            notes = measure_data.get_notes_by_staff(clef_type)
            
            if not notes:
                # 创建整小节休止符
                rest = music21.note.Rest()
                rest.duration.type = 'whole'  # 显式设置为全音符
                staff.append(rest)
            else:
                # 按位置排序音符
                sorted_notes = sorted(notes, key=lambda n: (n.position_beats % BEATS_PER_MEASURE, n.x))
                measure_start = measure_data.get_measure_start_beat()
                current_beat = 0.0
                
                # 处理小节内的音符和休止符
                for i, note in enumerate(sorted_notes):
                    # 计算当前音符前的休止符
                    note_position = note.position_beats - measure_start
                    if note_position > current_beat:
                        rest_length = note_position - current_beat
                        if rest_length == 2.0:  # 半音符休止符
                            rest = music21.note.Rest()
                            rest.duration.type = 'half'
                        else:
                            rest = music21.note.Rest(quarterLength=rest_length)
                        staff.append(rest)
                    
                    # 添加音符（四分音符）
                    m21_note = music21.note.Note(note.pitch_name)
                    m21_note.duration.type = 'quarter'
                    staff.append(m21_note)
                    current_beat = note_position + 1.0  # 更新当前拍位置
                
                # 添加小节末尾的休止符
                if current_beat < BEATS_PER_MEASURE:
                    rest = music21.note.Rest(quarterLength=BEATS_PER_MEASURE - current_beat)
                    staff.append(rest)
            
            measure.insert(0, staff)
        
        if self.debugger:
            self.debugger.compare_measure(measure_number, measure_data, measure)
        
        return measure
    
    def _create_measure(self, measure_data: Measure, clef_type: ClefType) -> music21.stream.Measure:
        """创建单个小节，确保严格遵守JSON中的音符结构"""
        measure = music21.stream.Measure(number=measure_data.number)
        
        # 获取当前谱表的音符，严格按照JSON中的顺序
        notes = measure_data.get_notes_by_staff(clef_type)
        
        # 调试输出
        if self.debugger:
            print(f"\nMeasure {measure_data.number} {clef_type.value}:")
            for note in notes:
                print(f"  Note: {note.pitch_name}, Duration: {note.duration_type}, Position: {note.position_beats}")
        
        if not notes:
            # 创建整小节休止符
            rest = music21.note.Rest()
            rest.duration.type = 'whole'
            measure.append(rest)
        else:
            # 检查是否为整小节单音符
            if len(notes) == 1 and notes[0].duration_beats == BEATS_PER_MEASURE:
                note = notes[0]
                m21_note = music21.note.Note(note.pitch_name)
                m21_note.duration.type = 'whole'
                measure.append(m21_note)
            else:
                # 处理多个音符的情况
                for note in notes:
                    duration_info = note.get_duration_info()
                    m21_note = music21.note.Note(note.pitch_name)
                    m21_note.duration.type = duration_info.type_name
                    measure.append(m21_note)
        
        return measure