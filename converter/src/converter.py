# src/converter.py
from typing import List, Optional, Tuple
import music21
from src.constants import (
    Note, Score, ClefType, Measure,
    TIME_SIGNATURE, BEATS_PER_MEASURE, STAFF_SPLIT_Y, KEY_SIGNATURE
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
        self.debug_measures = []  # 添加用于存储需要调试的小节号列表
        if debugger and debugger.measure_numbers:
            self.debug_measures = debugger.measure_numbers
    
    def convert(self) -> music21.stream.Score:
        """将JSON格式的乐谱转换为music21格式"""
        score = music21.stream.Score()
        
        # 添加元数据（包括标题、作者等）
        self.score_data.add_metadata_to_score(score)
        
        treble_part = music21.stream.Part()
        bass_part = music21.stream.Part()
        
        # 设置谱号
        treble_part.insert(0, music21.clef.TrebleClef())
        bass_part.insert(0, music21.clef.BassClef())
        
        # 处理所有小节
        for measure_data in self.score_data.measures:
            treble_measure, bass_measure = self._process_measure(measure_data)
            
            # 添加时间签名到第一小节
            if measure_data.number == 1:
                ts = music21.meter.TimeSignature(TIME_SIGNATURE)
                treble_measure.timeSignature = ts
                bass_measure.timeSignature = ts
            
            treble_part.append(treble_measure)
            bass_part.append(bass_measure)
        
        score.insert(0, treble_part)
        score.insert(0, bass_part)
        
        # 添加速度标记
        self.score_data.add_tempo_to_score(score)
        
        return score
    
    def _process_measure(self, measure_data: Measure) -> Tuple[music21.stream.Measure, music21.stream.Measure]:
        """处理单个小节"""
        treble_measure = music21.stream.Measure(number=measure_data.number)
        bass_measure = music21.stream.Measure(number=measure_data.number)
        
        # 根据 y 坐标分离高音谱表和低音谱表的音符
        treble_notes = []
        bass_notes = []
        
        for note in measure_data.notes:
            # 使用 STAFF_SPLIT_Y 常量作为分界线
            if note.y >= STAFF_SPLIT_Y:  # y坐标大于分界线的放在高音谱
                treble_notes.append(note)
            else:  # y坐标小于分界线的放在低音谱
                bass_notes.append(note)
        
        # 处理高音谱表
        self._fill_staff_measure(
            measure=treble_measure,
            notes=treble_notes,
            measure_number=measure_data.number,
            staff_type=ClefType.TREBLE,
            measure_start=measure_data.start_position_beats
        )
        
        # 处理低音谱表
        self._fill_staff_measure(
            measure=bass_measure,
            notes=bass_notes,
            measure_number=measure_data.number,
            staff_type=ClefType.BASS,
            measure_start=measure_data.start_position_beats
        )
        
        # 只在指定的小节号时输出调试信息
        if self.debugger and (not self.debug_measures or measure_data.number in self.debug_measures):
            print(f"Debug: Measure {measure_data.number}")
            print(f"  Treble: {[(n.nameWithOctave if isinstance(n, music21.note.Note) else 'Rest', n.duration.type, n.duration.dots, n.offset) for n in treble_measure.notes]}")
            print(f"  Bass: {[(n.nameWithOctave if isinstance(n, music21.note.Note) else 'Rest', n.duration.type, n.duration.dots, n.offset) for n in bass_measure.notes]}")
        
        return treble_measure, bass_measure
    
    def _fill_staff_measure(
        self,
        measure: music21.stream.Measure,
        notes: List[Note],
        measure_number: int,
        staff_type: ClefType,
        measure_start: float
    ):
        """填充单个谱表的小节"""
        if not notes:
            # 添加全小节休止符
            rest = music21.note.Rest()
            rest.duration = DurationManager.create_duration(
                quarter_length=BEATS_PER_MEASURE
            )
            measure.append(rest)
            return

        # 按位置分组音符
        position_groups = {}
        for note in sorted(notes, key=lambda n: n.position_beats):
            pos = note.position_beats
            if pos not in position_groups:
                position_groups[pos] = []
            position_groups[pos].append(note)
        
        # 处理每个位置的音符
        for pos, pos_notes in position_groups.items():
            relative_pos = pos - measure_start
            
            if len(pos_notes) > 1:
                # 创建和弦
                pitches = []
                for note in pos_notes:
                    if note.pitch_name.lower() != 'rest':
                        pitches.append(note.pitch_name)
                
                if pitches:  # 只有当有实际音符时才创建和弦
                    chord = music21.chord.Chord(pitches)
                    # 使用第一个音符的时值
                    chord.duration = DurationManager.create_duration(
                        duration_type=pos_notes[0].duration_type,
                        quarter_length=pos_notes[0].duration_beats * BEATS_PER_MEASURE
                    )
                    measure.insert(relative_pos, chord)
                else:
                    # 如果所有音符都是休止符，只添加一个休止符
                    rest = music21.note.Rest()
                    rest.duration = DurationManager.create_duration(
                        duration_type=pos_notes[0].duration_type,
                        quarter_length=pos_notes[0].duration_beats * BEATS_PER_MEASURE
                    )
                    measure.insert(relative_pos, rest)
            else:
                # 单个音符
                note = pos_notes[0]
                m21_note = music21.note.Note(note.pitch_name) if note.pitch_name.lower() != 'rest' else music21.note.Rest()
                m21_note.duration = DurationManager.create_duration(
                    duration_type=note.duration_type,
                    quarter_length=note.duration_beats * BEATS_PER_MEASURE
                )
                measure.insert(relative_pos, m21_note)
    
    def _process_chord_notes(self, notes: List[Note], measure_start: float) -> List[music21.chord.Chord]:
        """处理同一位置的多个音符（和弦）"""
        # 按位置分组音符
        position_groups = {}
        for note in notes:
            pos = note.position_beats
            if pos not in position_groups:
                position_groups[pos] = []
            position_groups[pos].append(note)
        
        chords = []
        for pos, chord_notes in position_groups.items():
            if len(chord_notes) > 1:
                # 创建和弦
                pitches = [note.pitch_name for note in chord_notes]
                chord = music21.chord.Chord(pitches)
                # 使用第一个音符的时值
                chord.duration = DurationManager.create_duration(
                    duration_type=chord_notes[0].duration_type,
                    quarter_length=chord_notes[0].duration_beats * BEATS_PER_MEASURE
                )
                chord.offset = pos - measure_start
                chords.append(chord)
            else:
                # 单个音符
                note = chord_notes[0]
                m21_note = music21.note.Note(note.pitch_name)
                m21_note.duration = DurationManager.create_duration(
                    duration_type=note.duration_type,
                    quarter_length=note.duration_beats * BEATS_PER_MEASURE
                )
                m21_note.offset = pos - measure_start
                chords.append(m21_note)
        
        return chords
    
    @classmethod
    def from_json(cls, json_path: str) -> 'ScoreConverter':
        """从JSON文件创建ScoreConverter对象"""
        # Score.from_json 现在会自动处理文件名
        score = Score.from_json(json_path)
        return cls(score)