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
    
    # 添加最小间隔阈值常量
    MIN_GAP_THRESHOLD = 0.01
    
    def __init__(self, score_data: Score, debugger: Optional[ScoreDebugger] = None):
        self.score_data = score_data
        self.debugger = debugger
        self.debug_measures = []  # 添加用于存储需要调试的小节号列表
        if debugger and debugger.measure_numbers:
            self.debug_measures = debugger.measure_numbers
        # 添加连音线跟踪字典 {(pitch_midi_note, staff_type): music21.note.Note}
        self.tie_starts = {}
    
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
        
        # 只在第一小节添加拍号
        if measure_data.number == 1:
            # 使用Score对象的time_signature而不是全局常量
            ts = music21.meter.TimeSignature(self.score_data.time_signature)
            treble_measure.timeSignature = ts
            bass_measure.timeSignature = ts
        
        # 只在指定的小节号时输出调试信息
        if self.debugger and (not self.debug_measures or measure_data.number in self.debug_measures):
            print(f"Debug: Measure {measure_data.number}")
            print(f"  Treble: {[(n.nameWithOctave if isinstance(n, music21.note.Note) else 'Rest', n.duration.type, n.duration.dots, n.offset) for n in treble_measure.notes]}")
            print(f"  Bass: {[(n.nameWithOctave if isinstance(n, music21.note.Note) else 'Rest', n.duration.type, n.duration.dots, n.offset) for n in bass_measure.notes]}")
        
        return treble_measure, bass_measure
    
    def _create_rest_with_duration(self, quarter_length: float) -> music21.note.Rest:
        """创建指定时值的休止符"""
        rest = music21.note.Rest()
        rest.duration = DurationManager.create_duration(
            quarter_length=quarter_length
        )
        return rest
    
    def _fill_staff_measure(
        self,
        measure: music21.stream.Measure,
        notes: List[Note],
        measure_number: int,
        staff_type: ClefType,
        measure_start: float
    ):
        """填充单个谱表的小节"""
        # 设置当前小节的调试信息
        DurationManager.set_debug_info(
            debug_measures=self.debug_measures,
            current_measure=measure_number,
            debug_enabled=self.debugger is not None
        )
        
        if not notes:
            # 添加全小节休止符
            beats_per_measure = float(self.score_data.time_signature.split('/')[0])
            rests = DurationManager.create_rest_with_duration(beats_per_measure)
            for rest in rests:
                measure.append(rest)
            return

        # 创建临时Stream来组织音符
        temp_stream = music21.stream.Stream()
        last_end_position = 0.0
        
        # 按位置分组音符
        position_groups = {}
        for note in sorted(notes, key=lambda n: n.position_beats):
            pos = note.position_beats
            if pos not in position_groups:
                position_groups[pos] = []
            position_groups[pos].append(note)
        
        # 处理每个位置的音符
        for pos, pos_notes in sorted(position_groups.items()):
            relative_pos = pos - measure_start
            
            # 处理音符间的间隔，添加最小间隔阈值检查
            gap = relative_pos - last_end_position
            if gap > self.MIN_GAP_THRESHOLD:  # 只有当间隔大于阈值时才添加休止符
                rests = DurationManager.create_rest_with_duration(gap)
                current_pos = last_end_position
                for rest in rests:
                    temp_stream.insert(current_pos, rest)
                    current_pos += rest.duration.quarterLength
            
            # 处理音符或和弦
            if len(pos_notes) > 1:
                chord = self._create_chord_with_ties(pos_notes, staff_type)
                if chord:
                    temp_stream.insert(relative_pos, chord)
                    last_end_position = relative_pos + chord.duration.quarterLength
            else:
                note = pos_notes[0]
                m21_note = self._create_note_with_ties(note, staff_type)
                temp_stream.insert(relative_pos, m21_note)
                last_end_position = relative_pos + m21_note.duration.quarterLength
        
        # 处理小节末尾的剩余空间
        beats_per_measure = float(self.score_data.time_signature.split('/')[0])
        remaining_duration = beats_per_measure - last_end_position
        if remaining_duration > self.MIN_GAP_THRESHOLD:  # 同样对末尾的间隔应用阈值检查
            rests = DurationManager.create_rest_with_duration(remaining_duration)
            current_pos = last_end_position
            for rest in rests:
                temp_stream.insert(current_pos, rest)
                current_pos += rest.duration.quarterLength
        
        # 将临时Stream中的内容添加到实际小节中
        for element in temp_stream:
            measure.insert(element.offset, element)
            
        # 找出所有八分音符
        eighth_notes = []
        for note in measure.notes:
            if isinstance(note, music21.note.Note) and note.duration.type == 'eighth':
                eighth_notes.append(note)
            elif isinstance(note, music21.chord.Chord) and note.duration.type == 'eighth':
                # 对于和弦，我们只需要处理第一个音符的beam
                eighth_notes.append(note)
        
        # 按照位置排序
        eighth_notes.sort(key=lambda n: n.offset)
        
        # 找出需要连接的八分音符组
        beam_groups = []
        current_group = []
        
        for i in range(len(eighth_notes)):
            if not current_group:
                current_group.append(eighth_notes[i])
            else:
                # 计算与前一个音符的间隔
                prev_note = current_group[-1]
                curr_note = eighth_notes[i]
                gap = curr_note.offset - (prev_note.offset + prev_note.duration.quarterLength)
                
                # 如果间隔很小，说明是连续的
                if gap < self.MIN_GAP_THRESHOLD:
                    current_group.append(curr_note)
                else:
                    # 如果当前组有两个或以上的音符，保存它
                    if len(current_group) >= 2:
                        beam_groups.append(current_group)
                    # 开始新的组
                    current_group = [curr_note]
        
        # 处理最后一组
        if len(current_group) >= 2:
            beam_groups.append(current_group)
        
        # 为每组音符设置beam
        for group in beam_groups:
            for i, note in enumerate(group):
                if i == 0:
                    note.beams.fill('eighth', 'start')
                elif i == len(group) - 1:
                    note.beams.fill('eighth', 'stop')
                else:
                    note.beams.fill('eighth', 'continue')
                    
        # 让music21处理其他beam情况
        measure.makeBeams()
    
    def _create_note_with_ties(self, note: Note, staff_type: ClefType) -> music21.note.Note:
        """创建带有连音线的音符"""
        if note.pitch_name.lower() == 'rest':
            return music21.note.Rest()
        
        m21_note = music21.note.Note(note.pitch_name)
        m21_note.duration = DurationManager.create_duration(
            duration_type=note.duration_type,
            quarter_length=note.duration_beats * BEATS_PER_MEASURE
        )
        
        # 处理升降号
        if note.accidental:
            m21_note.pitch.accidental = music21.pitch.Accidental(note.accidental)
            if note.accidental_cautionary:
                m21_note.pitch.accidental.cautionary = True
                m21_note.pitch.accidental.displayType = "cautionary"
        
        # 处理连音线
        if note.tie_type and note.pitch_midi_note is not None:
            tie_key = (note.pitch_midi_note, staff_type)
            
            if note.tie_type == 'start':
                # 保存开始音符
                self.tie_starts[tie_key] = m21_note
                m21_note.tie = music21.tie.Tie('start')
                
            elif note.tie_type == 'stop':
                # 查找对应的开始音符
                start_note = self.tie_starts.get(tie_key)
                if start_note:
                    m21_note.tie = music21.tie.Tie('stop')
                    # 清除已使用的开始音符
                    del self.tie_starts[tie_key]
        
        return m21_note
    
    def _create_chord_with_ties(self, notes: List[Note], staff_type: ClefType) -> Optional[music21.chord.Chord]:
        """创建带有连音线的和弦"""
        pitches = []
        note_objects = []
        
        for note in notes:
            if note.pitch_name.lower() != 'rest':
                m21_note = self._create_note_with_ties(note, staff_type)
                pitches.append(note.pitch_name)
                note_objects.append(m21_note)
        
        if not pitches:
            return None
        
        chord = music21.chord.Chord(pitches)
        # 使用第一个音符的时值
        chord.duration = DurationManager.create_duration(
            duration_type=notes[0].duration_type,
            quarter_length=notes[0].duration_beats * BEATS_PER_MEASURE
        )
        
        # 将连音线和升降号信息从单个音符转移到和弦的音符
        for i, m21_note in enumerate(note_objects):
            if hasattr(m21_note, 'tie') and m21_note.tie:
                chord.notes[i].tie = m21_note.tie
            if hasattr(m21_note.pitch, 'accidental') and m21_note.pitch.accidental:
                chord.notes[i].pitch.accidental = m21_note.pitch.accidental
        
        return chord
    
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
        score = Score.from_json(json_path, debug_enabled=cls.debugger is not None)
        return cls(score)