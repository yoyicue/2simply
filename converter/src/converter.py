# src/converter.py
from typing import List, Optional, Tuple
import music21
from src.constants import (
    Note, Score, ClefType, Measure,
    TIME_SIGNATURE, KEY_SIGNATURE, BEATS_PER_MEASURE
)
from src.debug import ScoreDebugger
from src.duration import DurationManager
import json

class ScoreConverter:
    """乐谱转换器"""
    
    def __init__(self, score_data: Score, debugger: Optional[ScoreDebugger] = None):
        self.score_data = score_data
        self.debugger = debugger
    
    def convert(self) -> music21.stream.Score:
        """将JSON格式的乐谱转换为music21格式"""
        score = music21.stream.Score()
        
        # 创建高音谱表和低音谱表
        treble_part = self._create_part(ClefType.TREBLE)
        bass_part = self._create_part(ClefType.BASS)
        
        # 处理每个小节
        for measure in self.score_data.measures:
            treble_measure, bass_measure = self._process_measure(measure)
            treble_part.append(treble_measure)
            bass_part.append(bass_measure)
        
        # 将声部添加到乐谱
        score.insert(0, treble_part)
        score.insert(0, bass_part)
        
        if self.debugger:
            print(f"Debug: Created Score with {len(self.score_data.measures)} measures")
        
        return score
    
    def _create_part(self, clef_type: ClefType) -> music21.stream.Part:
        """创建声部并设置谱号"""
        part = music21.stream.Part()
        if clef_type == ClefType.TREBLE:
            part.append(music21.clef.TrebleClef())
        elif clef_type == ClefType.BASS:
            part.append(music21.clef.BassClef())
        # 其他谱号类型可以在此添加
        return part
    
    def _process_measure(self, measure_data: Measure) -> Tuple[music21.stream.Measure, music21.stream.Measure]:
        print(f"Processing Measure {measure_data.number} with startPositionBeats {measure_data.startPositionBeats}")
        treble_notes = [n for n in measure_data.notes if n.staff == ClefType.TREBLE]
        bass_notes = [n for n in measure_data.notes if n.staff == ClefType.BASS]
        
        treble_measure = music21.stream.Measure(number=measure_data.number)
        bass_measure = music21.stream.Measure(number=measure_data.number)
        
        # 处理高音谱表音符
        self._add_notes_to_measure(treble_measure, treble_notes, measure_data.startPositionBeats)
        
        # 处理低音谱表音符
        self._add_notes_to_measure(bass_measure, bass_notes, measure_data.startPositionBeats)
        
        if self.debugger:
            self.debugger.compare_measure(measure_data.number, measure_data, treble_measure, bass_measure)
        
        return treble_measure, bass_measure
    
    def _add_notes_to_measure(self, measure: music21.stream.Measure, notes: List[Note], measure_start_beats: float):
        """将音符和休止符添加到小节中，考虑相对节拍位置"""
        if not notes:
            # 如果没有音符，添加一个全小节休止符
            rest = music21.note.Rest()
            rest.duration = DurationManager.create_music21_duration(BEATS_PER_MEASURE)
            measure.append(rest)
            print(f"Debug: Added Rest with quarterLength: {rest.duration.quarterLength}, type: {rest.duration.type}, dots: {rest.duration.dots}")
        else:
            # 按照 position_beats 排序音符
            sorted_notes = sorted(notes, key=lambda n: n.positionBeats)
            current_beat = 0.0
            print(f"Debug: Current beat starts at {current_beat}")
            
            for note in sorted_notes:
                # 计算相对于小节的节拍位置
                relative_position_beats = note.positionBeats - measure_start_beats
                if relative_position_beats < 0.0 or relative_position_beats > BEATS_PER_MEASURE:
                    print(f"Warning: Note positionBeats {note.positionBeats} out of measure range in Measure {measure.number}")
                    continue  # 跳过无效音符
                print(f"Debug: Note position in measure: {relative_position_beats}, Current beat: {current_beat}")
                
                # 计算当前音符前的休止符
                if relative_position_beats > current_beat:
                    rest_length = relative_position_beats - current_beat
                    rest = music21.note.Rest()
                    rest.duration = DurationManager.create_music21_duration(rest_length)
                    measure.append(rest)
                    print(f"Debug: Added Rest with quarterLength: {rest.duration.quarterLength}, type: {rest.duration.type}, dots: {rest.duration.dots}")
                
                # 添加音符
                m21_note = music21.note.Note(note.pitchName)
                m21_note.duration = DurationManager.create_music21_duration(note.durationBeats)
                measure.append(m21_note)
                print(f"Debug: Added Note {m21_note.nameWithOctave} with quarterLength: {m21_note.duration.quarterLength}, type: {m21_note.duration.type}, dots: {m21_note.duration.dots}")
                
                # 更新当前节拍
                current_beat = relative_position_beats + note.durationBeats
            
            # 检查小节总节拍是否超过限制
            if current_beat > BEATS_PER_MEASURE + 0.001:
                print(f"Error: Measure {measure.number} exceeds beats per measure. Total beats: {current_beat}")
            
            # 添加小节末尾的休止符
            remaining_length = BEATS_PER_MEASURE - current_beat
            if remaining_length > 0.001:
                rest = music21.note.Rest()
                rest.duration = DurationManager.create_music21_duration(remaining_length)
                measure.append(rest)
                print(f"Debug: Added Rest with quarterLength: {rest.duration.quarterLength}, type: {rest.duration.type}, dots: {rest.duration.dots}")

class Score:
    def __init__(self, measures: List[Measure]):
        self.measures = measures

    @classmethod
    def from_json(cls, json_path: str) -> 'Score':
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        measures = []
        for m in data.get('measures', []):
            print(f"Parsing Measure {m.get('number')}, startPositionBeats: {m.get('startPositionBeats')}")
            notes = []
            for n in m.get('notes', []):
                note = Note(
                    staff=n.get('staff'),
                    pitchName=n.get('pitchName'),
                    durationBeats=n.get('durationBeats'),
                    durationSeconds=n.get('durationSeconds'),
                    durationType=n.get('durationType'),
                    pitchMidiNote=n.get('pitchMidiNote'),
                    positionBeats=n.get('positionBeats'),
                    positionSeconds=n.get('positionSeconds'),
                    tieType=n.get('tieType'),
                    width=n.get('width'),
                    x=n.get('x'),
                    y=n.get('y')
                )
                notes.append(note)
            
            measure = Measure(
                number=m.get('number'),
                height=m.get('height'),
                staffDistance=m.get('staffDistance'),
                width=m.get('width'),
                x=m.get('x'),
                y=m.get('y'),
                notes=notes,
                startPositionBeats=m.get('startPositionBeats', 0.0),  # 设置默认值
                startPositionSeconds=m.get('startPositionSeconds', 0.0),  # 设置默认值
            )
            measures.append(measure)
        
        return cls(measures)