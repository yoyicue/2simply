# src/converter.py
from typing import List, Optional, Tuple
import music21
from src.constants import (
    Note, Score, ClefType, Measure,
    TIME_SIGNATURE, BEATS_PER_MEASURE
)
from src.debug import ScoreDebugger
from src.duration import DurationManager
import json
import copy

class ScoreConverter:
    """乐谱转换器"""
    
    def __init__(self, score_data: Score, debugger: Optional[ScoreDebugger] = None):
        self.score_data = score_data
        self.debugger = debugger
    
    def convert(self) -> music21.stream.Score:
        """将JSON格式的乐谱转换为music21格式"""
        score = music21.stream.Score()
        treble_part = music21.stream.Part()
        bass_part = music21.stream.Part()
        
        # 设置谱号
        treble_part.insert(0, music21.clef.TrebleClef())
        bass_part.insert(0, music21.clef.BassClef())
        
        # 创建一个集合来跟踪已处理的小节号
        processed_measures = set()
        total_measures = len(self.score_data.measures)
        
        # 确保按小节号顺序处理
        sorted_measures = sorted(self.score_data.measures, key=lambda m: m.number)
        
        for measure_data in sorted_measures:
            measure_number = measure_data.number
            
            # 验证小节号的有效性
            if measure_number < 1 or measure_number > total_measures:
                print(f"Warning: Invalid measure number {measure_number}, skipping...")
                continue
            
            # 跳过已处理的小节
            if measure_number in processed_measures:
                continue
            
            processed_measures.add(measure_number)
            
            # 处理小节内容
            treble_measure, bass_measure = self._process_measure(measure_data)
            
            # 添加时间签名到第一小节
            if measure_number == 1:
                ts = music21.meter.TimeSignature('4/4')
                treble_measure.timeSignature = ts
                bass_measure.timeSignature = ts
            
            # 添加小节到对应声部
            treble_part.append(treble_measure)
            bass_part.append(bass_measure)
            
            # 调试输出
            if self.debugger and self.debugger.should_debug(measure_number):
                self.debugger.compare_measure(
                    measure_number=measure_number,
                    measure_data=measure_data,
                    treble_measure=treble_measure,
                    bass_measure=bass_measure
                )
        
        # 添加声部到总谱
        score.insert(0, treble_part)
        score.insert(0, bass_part)
        
        if self.debugger:
            print(f"Debug: Created Score with {total_measures} measures")
            print(f"Debug: Processed measure numbers: {sorted(processed_measures)}")
            if len(processed_measures) != total_measures:
                print(f"Warning: Expected {total_measures} measures but processed {len(processed_measures)}")
        
        return score
    
    def _process_measure(self, measure_data: Measure) -> Tuple[music21.stream.Measure, music21.stream.Measure]:
        """处理单个小节"""
        measure_number = measure_data.number
        
        # 创建小节
        treble_measure = music21.stream.Measure(number=measure_number)
        bass_measure = music21.stream.Measure(number=measure_number)
        
        # 获取高音谱和低音谱的音符
        treble_notes = measure_data.get_notes_by_staff(ClefType.TREBLE)
        bass_notes = measure_data.get_notes_by_staff(ClefType.BASS)
        
        if self.debugger:
            print(f"Debug: Treble Notes in Measure {measure_number}: {[n.pitch_name for n in treble_notes]}")
            print(f"Debug: Bass Notes in Measure {measure_number}: {[n.pitch_name for n in bass_notes]}")
        
        # 填充音符到对应的小节
        self._fill_measure(treble_measure, treble_notes, measure_number, "Treble", measure_data.start_position_beats)
        self._fill_measure(bass_measure, bass_notes, measure_number, "Bass", measure_data.start_position_beats)
        
        return treble_measure, bass_measure
    
    def _fill_measure(
        self,
        measure: music21.stream.Measure,
        notes: List[Note],
        measure_number: int,
        staff: str,
        measure_start_beats: float
    ):
        """填充音符到节"""
        if not notes:
            # 如果没有音符，添加一个全小节休止符
            rest = music21.note.Rest()
            rest.duration = DurationManager.create_duration('whole')
            measure.append(rest)
            if self.debugger:
                print(f"Debug: Added full measure Rest in measure {measure_number} ({staff})")
            return
        
        current_offset = 0.0
        for note in notes:
            # 计算相对于小节的位置信息
            relative_position = note.position_beats - measure_start_beats
            
            # 确保相对位置不为负
            if relative_position < 0:
                if self.debugger:
                    print(f"Debug: Skipping note {note.pitch_name} with negative relative position in measure {measure_number} ({staff})")
                continue
            
            # 计算间隙并添加休止符
            gap = relative_position - current_offset
            if gap > 0.001:  # 使用阈值避免浮点数比较问题
                rest = music21.note.Rest()
                rest.duration = DurationManager.create_duration(quarter_length=gap)
                measure.append(rest)
                if self.debugger:
                    print(f"Debug: Added Rest duration={gap} at position={current_offset} in measure {measure_number} ({staff})")
            
            # 添加音符或休止符
            if note.pitch_name.lower() != 'rest':
                m21_note = music21.note.Note(note.pitch_name)
            else:
                m21_note = music21.note.Rest()
                
            # 使用音符的实际时值
            m21_note.duration = DurationManager.create_duration(quarter_length=note.duration_beats)
            measure.append(m21_note)
            
            if self.debugger:
                print(f"Debug: Added {note.pitch_name} duration={note.duration_beats} at position={relative_position} in measure {measure_number} ({staff})")
            
            current_offset = relative_position + note.duration_beats
            
            # 检查是否超出小节长度
            if current_offset > BEATS_PER_MEASURE + 0.001:  # 添加小阈值避免浮点数比较问题
                if self.debugger:
                    print(f"Debug: Note {note.pitch_name} exceeds measure length in measure {measure_number} ({staff})")
                raise ValueError(f"Note {note.pitch_name} at position {relative_position} exceeds measure length in measure {measure_number} ({staff})")
        
        # 添加小节末尾的休止符
        remaining_beats = BEATS_PER_MEASURE - current_offset
        if remaining_beats > 0.001:  # 使用小阈值避免浮点数比较问题
            final_rest = music21.note.Rest()
            final_rest.duration = DurationManager.create_duration(quarter_length=remaining_beats)
            measure.append(final_rest)
            if self.debugger:
                print(f"Debug: Added final Rest of length {remaining_beats} at position={current_offset} in measure {measure_number} ({staff})")

    @classmethod
    def from_json(cls, json_path: str) -> 'ScoreConverter':
        """从JSON文件创建ScoreConverter对象"""
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Use the Score class from constants.py
        score = Score.from_json(json_path)
        return cls(score.measures)