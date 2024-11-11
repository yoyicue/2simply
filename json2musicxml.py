from music21 import note, pitch, stream, metadata, meter, tempo, clef, layout, bar, spanner, instrument, midi, volume, defaults, chord
from dataclasses import dataclass, fields
from typing import Dict, List, Optional, Tuple, Union, Any
import json
import re
import traceback
import argparse
from copy import deepcopy
from collections import OrderedDict
from enum import Enum
import bisect
from collections import defaultdict
from fractions import Fraction

# 1. 首先定义时值管理类
@dataclass(frozen=True)
class DurationInfo:
    """时值信息数据类"""
    type_name: str          # 时值类型名称
    quarter_length: float   # 四分音符长度
    beats: float           # 拍数
    description: str       # 描述

class DurationManager:
    """统一的时值管理类"""
    
    # 标准时值映射表 (type_name, quarter_length, beats, description)
    DURATIONS = {
        'whole': DurationInfo('whole', 4.0, 4.0, '全音符'),
        'half': DurationInfo('half', 2.0, 2.0, '二分音符'),
        'quarter': DurationInfo('quarter', 1.0, 1.0, '四分音符'),
        'eighth': DurationInfo('eighth', 0.5, 0.5, '八分音'),
        '16th': DurationInfo('16th', 0.25, 0.25, '十六分音符'),
        '32nd': DurationInfo('32nd', 0.125, 0.125, '三十二分音符'),
        # 带附点的音符
        'dotted-half': DurationInfo('half', 3.0, 3.0, '带附点的二分音符'),
        'dotted-quarter': DurationInfo('quarter', 1.5, 1.5, '带附点的四分音符'),
        'dotted-eighth': DurationInfo('eighth', 0.75, 0.75, '带附点的八分音符'),
        'dotted-16th': DurationInfo('16th', 0.375, 0.375, '带附点的十六分音符')
    }
    
    # 预先排序的时值列表，用于二分查找
    SORTED_QUARTER_LENGTHS = sorted(info.quarter_length for info in DURATIONS.values())
    
    @classmethod
    def get_duration_info(cls, quarter_length: float) -> DurationInfo:
        """
        根据四分音符时值获取最接近的标准时值信息
        Args:
            quarter_length: 四分音符时值
        Returns:
            DurationInfo: 时值信息对象
        """
        # 处理精度问题，四舍五入到3位小数
        rounded_length = round(quarter_length * 1000) / 1000
        
        # 如果是标准时值，直接返回
        for info in cls.DURATIONS.values():
            if abs(info.quarter_length - rounded_length) < 0.001:
                return info
        
        # 使用二查找找最接近的标准时值
        index = bisect.bisect_right(cls.SORTED_QUARTER_LENGTHS, rounded_length)
        if index == 0:
            closest_length = cls.SORTED_QUARTER_LENGTHS[0]
        else:
            # 比较前后两个值，选择最接近的
            prev_length = cls.SORTED_QUARTER_LENGTHS[index - 1]
            if index < len(cls.SORTED_QUARTER_LENGTHS):
                next_length = cls.SORTED_QUARTER_LENGTHS[index]
                closest_length = prev_length if abs(rounded_length - prev_length) <= abs(rounded_length - next_length) else next_length
            else:
                closest_length = prev_length
        
        # 返回对应的 DurationInfo
        for info in cls.DURATIONS.values():
            if abs(info.quarter_length - closest_length) < 0.001:
                return info
                
        # 如果没找到（不应该发生），返回默认值
        return cls.DURATIONS['quarter']
    
    @classmethod
    def get_duration_type(cls, beats: float) -> str:
        """
        根据拍数获取标准时值类型名称
        Args:
            beats: 拍数
        Returns:
            str: 时值类型名称
        """
        quarter_length = beats * 4.0  # 转换为四分音符时值
        return cls.get_duration_info(quarter_length).type_name
    
    @classmethod
    def get_quarter_length(cls, duration_type: str) -> float:
        """
        根据时值类型获取四分音符时值
        Args:
            duration_type: 时值类型名称
        Returns:
            float: 四分音符时值
        """
        return cls.DURATIONS.get(duration_type, cls.DURATIONS['quarter']).quarter_length

# 2. 然后是其他数据类...
@dataclass
class Note:
    """统一的音符数据结构"""
    pitch_name: str
    duration_beats: float
    duration_type: str
    y: float
    x: float = 0.0
    dynamics: float = 88.89
    staff: int = 1
    position: float = 0.0
    is_rest: bool = False

    @classmethod
    def from_dict(cls, data: Dict) -> 'Note':
        """从字典创建 Note 实例"""
        valid_fields = {
            "pitch_name": data.get("pitchName", ""),
            "duration_beats": float(data.get("durationBeats", 0.0)),
            "duration_type": data.get("durationType", ""),
            "y": float(data.get("y", 0.0)),
            "x": float(data.get("x", 0.0)),
            "dynamics": float(data.get("dynamics", 88.89)),
            "staff": int(data.get("staff", 1)),
            "position": float(data.get("position", 0.0)),
            "is_rest": data.get("pitchName", "").lower() == "rest"
        }
        return cls(**valid_fields)

@dataclass
class MeasureData:
    """JSON小节数据结构"""
    notes: List[Note]
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MeasureData':
        return cls(notes=[Note.from_dict(n) for n in data['notes']])

@dataclass
class ScoreData:
    """JSON乐谱数据结构"""
    measures: List[MeasureData]
    timeBeats: int = 4
    timeBeatType: int = 4
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ScoreData':
        return cls(
            measures=[MeasureData.from_dict(m) for m in data['measures']],
            timeBeats=data.get('timeBeats', 4),
            timeBeatType=data.get('timeBeatType', 4)
        )

@dataclass
class Measure:
    """小节数据类"""
    number: int
    notes: List[note.GeneralNote]

@dataclass
class Score:
    """乐谱数据类"""
    measures: List[Measure]
    time_beats: int = 4
    time_beat_type: int = 4

@dataclass
class TimeSignature:
    beats: int
    beat_type: int
    
    @property
    def quarter_length_per_measure(self) -> float:
        """返回每小节的四分音符量"""
        return (self.beats * 4.0) / self.beat_type

class DurationType(Enum):
    """音符类型枚举"""
    WHOLE = ('whole', 4.0)
    HALF = ('half', 2.0)
    QUARTER = ('quarter', 1.0)
    EIGHTH = ('eighth', 0.5)
    SIXTEENTH = ('16th', 0.25)
    
    def __init__(self, name: str, length: float):
        self.type_name = name
        self.quarter_length = length
    
    @classmethod
    def from_quarter_length(cls, quarter_length: float) -> 'DurationType':
        """根据四分音符时值获取对应的音符类型"""
        return min(cls, key=lambda x: abs(x.quarter_length - quarter_length))

@dataclass
class NoteConfig:
    """音配"""
    MEASURE_WIDTH: float = 200.0  # 小节宽度
    MEASURE_LENGTH: float = 4.0   # 4/4拍小节长度
    MIN_DURATION: float = 0.25    # 最小时值（十六分音符）
    STAFF_SPLIT_Y: float = -60    # 高低谱分界线

class StaffProcessor:
    """谱表处理器"""
    def __init__(self, config: NoteConfig = NoteConfig()):
        self.config = config
    
    def process_staff(self, notes: List[Note], is_treble: bool) -> List[note.GeneralNote]:
        """处理单个谱表的音符"""
        if not notes:
            return [self._create_whole_measure_rest()]
        
        # 按x坐标排序
        notes = sorted(notes, key=lambda n: n.x)
        result = []
        
        # 将小节分成16个等份（每份0.25）
        grid_positions = [i * 0.25 for i in range(17)]  # 0到4拍，步0.25
        current_position = 0.0
        
        for n in notes:
            # 将音符位置量化到网格
            note_position = self._quantize_to_grid(n.x / self.config.MEASURE_WIDTH * 4.0)
            
            # 添加间隙休止符
            while current_position < note_position:
                rest = self._create_rest(0.25)
                result.append(rest)
                current_position += 0.25
            
            # 添加音符
            new_note = self._create_note(n)
            result.append(new_note)
            current_position += 0.25  # 定使0.25拍
        
        # 充末尾休止符
        while current_position < 4.0:
            rest = self._create_rest(0.25)
            result.append(rest)
            current_position += 0.25
        
        return result

    def _quantize_to_grid(self, position: float) -> float:
        """将位置量化到0.25拍的网格上"""
        grid = [i * 0.25 for i in range(17)]  # 0到4拍，步长0.25
        return min(grid, key=lambda x: abs(x - position))

    def _create_rest(self, duration: float) -> note.Rest:
        """创建休止符"""
        r = note.Rest()
        duration_info = DurationManager.get_duration_info(duration)
        r.duration.quarterLength = duration_info.quarter_length
        r.duration.type = duration_info.type_name
        return r

    def _create_note(self, note_data: Note) -> note.Note:
        """创建音符"""
        n = note.Note(note_data.pitch_name)
        duration_info = DurationManager.get_duration_info(note_data.duration_beats * 4.0)
        n.duration.quarterLength = duration_info.quarter_length
        n.duration.type = duration_info.type_name
        n.volume.velocity = int(note_data.dynamics)
        n.style.absoluteX = note_data.x
        n.style.absoluteY = note_data.y
        return n

    def _normalize_duration(self, duration: float) -> float:
        """标准化时值"""
        standard_durations = [0.25, 0.5, 1.0, 2.0, 4.0]
        return min(standard_durations, key=lambda x: abs(x - duration))

    def _create_whole_measure_rest(self) -> note.Rest:
        """创建整小节休止符"""
        r = note.Rest()
        r.duration.quarterLength = self.config.MEASURE_LENGTH
        r.duration.type = DurationType.WHOLE.type_name
        return r

class MeasurePattern:
    """小节模式数据类"""
    def __init__(self, is_empty: bool, has_chord: bool = False, 
                 has_prerest: bool = False, note_groups: Dict = None):
        self.is_empty = is_empty
        self.has_chord = has_chord
        self.has_prerest = has_prerest
        self.note_groups = note_groups or {}

class MeasureProcessor:
    """小节处理器 - 使用策略模式处理不同类型的小节"""
    def __init__(self, time_signature: TimeSignature):
        """
        初始化小节处理器
        Args:
            time_signature: TimeSignature 对象，包含拍号信息
        """
        self.time_signature = meter.TimeSignature(f'{time_signature.beats}/{time_signature.beat_type}')
        self.measure_length = 4.0  # 标准化为4拍

    def create_measure(self, measure_number: int, notes: List[Note], is_first: bool = False) -> Tuple[stream.Measure, stream.Measure]:
        """创建高音谱表和低音谱表的小节"""
        # 按y坐标分离高音和低音谱表的音符
        treble_notes = sorted([n for n in notes if n.y > -60], key=lambda x: x.x)
        bass_notes = sorted([n for n in notes if n.y <= -60], key=lambda x: x.x)
        
        # 创建小节
        treble_measure = self._create_staff_measure(measure_number, treble_notes, is_treble=True, is_first=is_first)
        bass_measure = self._create_staff_measure(measure_number, bass_notes, is_treble=False, is_first=is_first)
        
        # 处理和弦（同时发声的音符）
        self._process_chords(treble_measure)
        self._process_chords(bass_measure)
        
        return treble_measure, bass_measure
    
    def _process_chords(self, measure: stream.Measure):
        """处理小节中的和弦"""
        # 使用 music21 的 chordify() 方法处理同时发声的音符
        if len(measure.notes) > 1:
            # 获取所有同时发声的音符
            chords = measure.chordify()
            if len(chords.notes) > 0:
                # 替换原有的音符
                measure.removeByClass(['Note', 'Chord'])
                for chord_element in chords:
                    if isinstance(chord_element, chord.Chord):
                        measure.insert(chord_element.offset, chord_element)
                    else:
                        measure.insert(chord_element.offset, chord_element)

    def _create_staff_measure(self, measure_number: int, notes: List[Note], is_treble: bool, is_first: bool) -> stream.Measure:
        """创建单谱表小"""
        m = stream.Measure(number=measure_number)
        
        if is_first:
            self._add_measure_attributes(m, is_treble)
        
        if not notes:
            # 空小节添加整小节休止符
            m.append(note.Rest(quarterLength=4.0))
            return m
        
        # 创建音符和休符
        current_position = 0.0
        for n in notes:
            # 计算音符位置
            note_position = n.x / 200.0 * 4.0
            
            # 添加之前的休止符（如果需要）
            if note_position > current_position:
                rest_duration = note_position - current_position
                if rest_duration > 0:
                    r = note.Rest()
                    r.duration.quarterLength = rest_duration
                    m.append(r)
            
            # 添加音符
            new_note = note.Note(n.pitch_name)
            new_note.duration.quarterLength = n.duration_beats
            new_note.volume.velocity = int(n.dynamics)
            m.append(new_note)
            
            current_position = note_position + n.duration_beats
        
        # 补充末尾休止符
        if current_position < 4.0:
            remaining_duration = 4.0 - current_position
            if remaining_duration > 0:
                r = note.Rest()
                r.duration.quarterLength = remaining_duration
                m.append(r)
        
        return m

    def _add_measure_attributes(self, measure: stream.Measure, is_treble: bool):
        """添加小节属性"""
        # 使用 music21 的 TimeSignature 对象
        measure.append(self.time_signature)
        measure.append(clef.TrebleClef() if is_treble else clef.BassClef())

    def debug_measure_comparison_detailed(self, original_notes, processed_measure, measure_idx):
        """详细比较原始音符和处理后的小节"""
        print(f"\n=== Measure {measure_idx} Comparison ===")
        
        print("\nOriginal Notes:")
        if hasattr(original_notes, 'notes'):
            notes_list = original_notes.notes
        else:
            notes_list = original_notes
            
        for i, note_data in enumerate(notes_list):
            print(f"\nNote {i+1}:")
            print(f"  Pitch: {note_data.pitch_name}")
            print(f"  Duration: {note_data.duration_beats} beats")
            print(f"  Position: x={note_data.x}, y={note_data.y}")
            print(f"  Staff: {note_data.staff}")
            print(f"  Dynamics: {note_data.dynamics}")
        
        print("\nProcessed Measure:")
        for i, element in enumerate(processed_measure.notesAndRests):
            print(f"\nElement {i+1}:")
            if isinstance(element, note.Note):
                print(f"  Type: Note")
                print(f"  Pitch: {element.nameWithOctave}")
                print(f"  Duration: {element.duration.quarterLength} quarter notes")
                print(f"  Duration Type: {element.duration.type}")
                if hasattr(element.style, 'absoluteX'):
                    print(f"  Position: x={element.style.absoluteX}, y={element.style.absoluteY}")
                print(f"  Velocity: {element.volume.velocity}")
            elif isinstance(element, note.Rest):
                print(f"  Type: Rest")
                print(f"  Duration: {element.duration.quarterLength} quarter notes")
                print(f"  Duration Type: {element.duration.type}")
            elif isinstance(element, chord.Chord):
                print(f"  Type: Chord")
                print(f"  Pitches: {[n.nameWithOctave for n in element.notes]}")
                print(f"  Duration: {element.duration.quarterLength} quarter notes")
                print(f"  Duration Type: {element.duration.type}")

    def _get_standard_duration_type(self, quarter_length: float) -> str:
        """获取标准时值类型"""
        return DurationManager.get_duration_info(quarter_length).type_name

    def _create_whole_rest(self) -> note.Rest:
        """创建整小节休止符"""
        rest = note.Rest()
        duration_info = DurationManager.DURATIONS['whole']
        rest.duration.quarterLength = duration_info.quarter_length
        rest.duration.type = duration_info.type_name
        return rest

    def debug_measure_comparison(self, json_notes: List[Note], measure: stream.Measure, measure_number: int):
        """比较JSON和生成的MusicXML小节"""
        print(f"\n=== Measure {measure_number} Comparison ===")
        
        print("\nJSON Notes:")
        for i, n in enumerate(json_notes):
            print(f"Note {i+1}:")
            print(f"  Pitch: {n.pitch_name}")
            print(f"  Duration: {n.duration_beats} beats")
            print(f"  Position: x={n.x}")
            print(f"  Staff: {'Treble' if n.y > -60 else 'Bass'}")
        
        print("\nGenerated MusicXML Notes:")
        for i, n in enumerate(measure.notesAndRests):
            if isinstance(n, note.Note):
                print(f"Element {i+1}: Note")
                print(f"  Pitch: {n.nameWithOctave}")
                print(f"  Duration: {n.duration.quarterLength} beats")
            elif isinstance(n, note.Rest):
                print(f"Element {i+1}: Rest")
                print(f"  Duration: {n.duration.quarterLength} beats")
            elif isinstance(n, chord.Chord):
                print(f"Element {i+1}: Chord")
                print(f"  Pitches: {[p.nameWithOctave for p in n.pitches]}")
                print(f"  Duration: {n.duration.quarterLength} beats")

# 4. MusicXML生成器 - 使 music21
class MusicXMLGenerator:
    def __init__(self, score: Score, score_data: ScoreData):
        self.score = score
        self.score_data = score_data  
        self.divisions = 10080
        self.time_signature = TimeSignature(
            beats=self.score.time_beats,
            beat_type=self.score.time_beat_type
        )
        self.processor = MeasureProcessor(self.time_signature)

    def generate(self, debug_measures: Optional[List[int]] = None) -> stream.Score:
        """生成MusicXML文档"""
        score_obj = stream.Score()
        
        # 创建声部
        treble_part = stream.Part(id='treble')
        bass_part = stream.Part(id='bass')

        # 设置初始属性
        for part in [treble_part, bass_part]:
            # 添加元数据
            part.insert(0, metadata.Metadata())
            # 添加拍号
            part.insert(0, meter.TimeSignature(f'{self.time_signature.beats}/{self.time_signature.beat_type}'))
            # 添加谱号
            part.insert(0, clef.TrebleClef() if part.id == 'treble' else clef.BassClef())

        # 处理每个小节
        for measure_idx, measure in enumerate(self.score.measures, 1):
            notes = measure.notes if isinstance(measure.notes, list) else measure.notes.notes
            
            # 分离高音和低音谱表的音符
            treble_notes = [n for n in notes if n.y > -60]
            bass_notes = [n for n in notes if n.y <= -60]
            
            # 如果是调试小节，打印详细信息
            if debug_measures and measure_idx in debug_measures:
                print(f"\n=== Measure {measure_idx} ===")
                
                # 打印原始数据
                print("\nOriginal Data:")
                print(f"Treble staff:")
                if not treble_notes:
                    print("  Whole measure rest")
                for n in sorted(treble_notes, key=lambda x: x.x):
                    print(f"  {n.pitch_name:<4} at x={n.x:>6.2f}, duration={n.duration_beats:>4.2f} beats, type={n.duration_type}")
                
                print(f"\nBass staff:")
                if not bass_notes:
                    print("  Whole measure rest")
                for n in sorted(bass_notes, key=lambda x: x.x):
                    print(f"  {n.pitch_name:<4} at x={n.x:>6.2f}, duration={n.duration_beats:>4.2f} beats, type={n.duration_type}")
                
                # 创建小节并打印生成的结构
                treble_measure = self._create_measure(measure_idx, treble_notes, True)
                bass_measure = self._create_measure(measure_idx, bass_notes, False)
                
                print("\nGenerated Structure:")
                print("Treble staff:")
                for elem in treble_measure.notesAndRests:
                    if isinstance(elem, note.Note):
                        print(f"  {elem.nameWithOctave:<4} duration={elem.duration.quarterLength:>4.2f} beats, type={elem.duration.type}")
                    else:
                        print(f"  Rest  duration={elem.duration.quarterLength:>4.2f} beats, type={elem.duration.type}")
                
                print("Bass staff:")
                for elem in bass_measure.notesAndRests:
                    if isinstance(elem, note.Note):
                        print(f"  {elem.nameWithOctave:<4} duration={elem.duration.quarterLength:>4.2f} beats, type={elem.duration.type}")
                    else:
                        print(f"  Rest  duration={elem.duration.quarterLength:>4.2f} beats, type={elem.duration.type}")
            
            # 创建小节
            treble_measure = self._create_measure(measure_idx, treble_notes, True)
            bass_measure = self._create_measure(measure_idx, bass_notes, False)
            
            treble_part.append(treble_measure)
            bass_part.append(bass_measure)
            
            # 验证小节时值总和
            self._validate_measure_duration(treble_measure, measure_idx, "treble")
            self._validate_measure_duration(bass_measure, measure_idx, "bass")
        
        score_obj.append(treble_part)
        score_obj.append(bass_part)
        
        # 最终处理
        for part in score_obj.parts:
            part.makeBeams(inPlace=True)
            part.makeMeasures(inPlace=True)
            part.makeNotation(inPlace=True)
        
        return score_obj

    def _debug_measure(self, measure, measure_idx):
        """调试输出小节信息"""
        print(f"\n=== Measure {measure_idx} Debug Info ===")
        notes = measure.notes if isinstance(measure.notes, list) else measure.notes.notes
        
        print("\nOriginal JSON notes:")
        for i, n in enumerate(notes):
            print(f"Note {i+1}:")
            print(f"  Pitch: {n.pitch_name}")
            print(f"  Duration: {n.duration_beats} beats")
            print(f"  Position: x={n.x}, y={n.y}")
            print(f"  Staff: {'Treble' if n.y > -60 else 'Bass'}")
            print(f"  Dynamics: {n.dynamics}")

    def _convert_to_music21_note(self, note_data: Note) -> note.Note:
        """将 Note 转换为 music21 Note 对象"""
        n = note.Note(note_data.pitch_name)
        n.duration.quarterLength = float(note_data.duration_beats) * 4.0
        n.duration.type = note_data.duration_type
        n.style.absoluteY = float(note_data.y)
        n.style.absoluteX = float(note_data.x)
        n.volume.velocity = int(float(note_data.dynamics))
        return n

    def _get_duration_type(self, quarter_length: float) -> str:
        """根据四分音符时值确定音符类型"""
        return DurationManager.get_duration_type(quarter_length)

    def _finalize_score(self, score_obj: stream.Score):
        """最终理谱，确保所有小节整"""
        for part in score_obj.parts:
            last_measure = part.getElementsByClass('Measure')[-1]
            if last_measure:
                actual_duration = sum(n.duration.quarterLength for n in last_measure.notes)
                expected_duration = 4.0  # 4/4拍
                
                if actual_duration < expected_duration:
                    remaining_duration = expected_duration - actual_duration
                    rest = note.Rest()
                    rest.duration.quarterLength = remaining_duration
                    rest.duration.type = self._get_duration_type(remaining_duration)
                    last_measure.append(rest)

    def _create_part(self, part_id: str) -> stream.Part:
        """创建的声部"""
        part = stream.Part()
        part.id = part_id
        
        attrs = layout.StaffLayout()
        attrs.staffLines = 5
        
        if part_id == 'treble':
            part.insert(0, clef.TrebleClef())
        else:
            part.insert(0, clef.BassClef())
        
        time_sig = meter.TimeSignature(f'{self.beats_per_measure}/{self.beat_type}')
        part.insert(0, time_sig)
        
        part.insert(0, attrs)
        
        return part

    def _create_measure(self, measure_number: int, notes: List[Note], is_treble: bool) -> stream.Measure:
        """创建单个小节，确保音符顺序和时值正确"""
        m = stream.Measure(number=measure_number)
        
        # 空小节处理 - 使用整小节休止符
        if not notes:
            whole_rest = note.Rest(quarterLength=4.0)
            whole_rest.duration.type = 'whole'
            m.append(whole_rest)
            return m
        
        # 按x坐标排序音符
        sorted_notes = sorted(notes, key=lambda n: n.x)
        current_offset = 0.0
        
        # 检查是否需要前置休止符（仅针对低音谱表且x>100的情况）
        if not is_treble and sorted_notes[0].x > 100:
            rest = note.Rest(quarterLength=2.0)
            rest.duration.type = 'half'
            m.insert(0, rest)
            current_offset = 2.0
        
        # 处理所有音符
        for n in sorted_notes:
            # 创建标准四分音符
            if n.is_rest:
                new_element = note.Rest(quarterLength=1.0)
            else:
                new_element = note.Note(n.pitch_name, quarterLength=1.0)
                new_element.volume.velocity = int(n.dynamics)
            new_element.duration.type = 'quarter'
            
            # 插入到正确位置
            m.insert(current_offset, new_element)
            current_offset += 1.0
        
        # 补充末尾休止符（如果需要）
        if current_offset < 4.0:
            remaining_duration = 4.0 - current_offset
            rest = note.Rest(quarterLength=remaining_duration)
            rest.duration.type = 'half' if remaining_duration == 2.0 else 'whole'
            m.append(rest)
        
        return m

    def _create_whole_rest(self) -> note.Rest:
        """创建整小节休止符"""
        r = note.Rest()
        whole_note_info = DurationManager.get_duration_info(4.0)
        r.duration.quarterLength = whole_note_info.quarter_length
        r.duration.type = whole_note_info.type_name
        return r

    def _get_duration_type(self, quarter_length: float) -> str:
        """根据四分音符时值确定音符类型"""
        duration_types = {
            4.0: 'whole',
            2.0: 'half',
            1.0: 'quarter',
            0.5: 'eighth',
            0.25: '16th'
        }
        return duration_types.get(quarter_length, 'quarter')

    def _analyze_measure_pattern(self, measure_notes: List[note.GeneralNote]) -> Dict:
        """分析小节模式，返回高音谱表和低音谱表的特征"""
        treble_notes = [n for n in measure_notes if n.style.absoluteY > -60]
        bass_notes = [n for n in measure_notes if n.style.absoluteY <= -60]
        
        pattern = {
            'treble': {
                'has_notes': bool(treble_notes),
                'notes': treble_notes
            },
            'bass': {
                'has_notes': bool(bass_notes),
                'notes': bass_notes,
                'has_prerest': False,  # Initialize with default value
                'chords': []  # Initialize with default value
            }
        }
        
        # 分析低音谱表模式
        if bass_notes:
            # 检查是否有前置空白
            first_note_x = min(n.style.absoluteX for n in bass_notes)
            pattern['bass']['has_prerest'] = first_note_x > 100  # 根据x坐标判断是否要前置休止符
            
            # 检查否有同时发的弦
            x_positions = {}
            for n in bass_notes:
                x = round(n.style.absoluteX, 2)
                if x not in x_positions:
                    x_positions[x] = []
                x_positions[x].append(n)
            
            pattern['bass']['chords'] = [
                notes for x, notes in x_positions.items()
                if len(notes) > 1 and all(n.duration.quarterLength == notes[0].duration.quarterLength for n in notes)
            ]
        
        return pattern

    def _normalize_x_to_offset(self, x: float, measure_width: float = 200.0) -> float:
        """将x坐标标准化为节拍偏移量"""
        return (x / measure_width) * 4.0

    def _validate_measure_duration(self, measure: stream.Measure, measure_number: int, staff: str):
        """验证小节时值"""
        total_duration = sum(n.duration.quarterLength for n in measure.notesAndRests)
        if abs(total_duration - 4.0) > 0.001:  # 允许小误差
            print(f"Warning: Measure {measure_number} ({staff}) has incorrect duration: {total_duration}")
            # 调整最后一个音符/休止符的时值
            last_element = measure.notesAndRests[-1]
            remaining_duration = 4.0 - (total_duration - last_element.duration.quarterLength)
            if remaining_duration > 0:
                duration_info = DurationManager.get_duration_info(remaining_duration)
                last_element.duration.quarterLength = duration_info.quarter_length
                last_element.duration.type = duration_info.type_name

# 3. JSON适配器
class JSONScoreAdapter:
    @staticmethod
    def parse(json_data: Dict) -> Score:
        """解析 JSON 数据为 Score 对象"""
        measures = []
        for i, measure_data in enumerate(json_data["measures"], 1):
            notes = [Note.from_dict(n) for n in measure_data["notes"]]
            # 按位置排序音符
            sorted_notes = sorted(notes, key=lambda x: (x.position, x.x))
            measures.append(Measure(number=i, notes=sorted_notes))
        
        # 创建 Score 对象
        return Score(
            measures=[Measure(i+1, notes) for i, notes in enumerate([m.notes for m in measures])],
            time_beats=json_data.get("timeBeats", 4),
            time_beat_type=json_data.get("timeBeatType", 4)
        )

def debug_measure_details(notes: List[Note], measure_label: str):
    """打印小节的详细信息"""
    print(f"\n{measure_label} Details:")
    print("Notes:")
    if not notes:
        print("  Empty measure (whole rest)")
        return
        
    # 按x坐标排序打印音符信息
    for note_obj in sorted(notes, key=lambda n: n.x):
        note_info = (
            f"  {'Rest' if note_obj.is_rest else note_obj.pitch_name} "
            f"at x={note_obj.x:.2f}, "
            f"duration={note_obj.duration_beats:.2f} beats"
        )
        if not note_obj.is_rest:
            note_info += f", dynamics={note_obj.dynamics:.2f}"
        print(note_info)

class MeasureValidator:
    """小节验证器 - 确保生成的MusicXML与JSON数据一致"""
    
    def __init__(self, score_data: ScoreData, score_obj: stream.Score):
        self.score_data = score_data  # 使 ScoreData 对象
        self.score_obj = score_obj

    def validate_measure(self, measure_number: int) -> Dict[str, Any]:
        """验证指定小节的音符是否与JSON一致"""
        measure_data = self.score_data.measures[measure_number - 1]

        # 按谱表分组音符
        notes = {
            'treble': [n for n in measure_data.notes if n.y > -60],
            'bass': [n for n in measure_data.notes if n.y <= -60]
        }

        validation_result = {
            'original': {
                'treble': self._format_original_notes(notes['treble']),
                'bass': self._format_original_notes(notes['bass'])
            },
            'generated': {
                'treble': [],  # 如果声部不存在则返回空列表
                'bass': []
            }
        }

        # 仅在声部存在时才获取生成的小节
        if self.score_obj.parts:
            if len(self.score_obj.parts) > 0:
                treble_measure = self.score_obj.parts[0].measure(measure_number)
                if treble_measure:
                    validation_result['generated']['treble'] = self._format_measure_notes(treble_measure)
            
            if len(self.score_obj.parts) > 1:
                bass_measure = self.score_obj.parts[1].measure(measure_number)
                if bass_measure:
                    validation_result['generated']['bass'] = self._format_measure_notes(bass_measure)

        return self._ensure_json_serializable(validation_result)

    def _safe_float(self, value: Optional[Any]) -> Optional[float]:
        """安全地将值转换为浮点数"""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _get_style_value(self, element: Any, attr: str) -> Optional[float]:
        """安全地获取样式属性值"""
        if hasattr(element, 'style') and hasattr(element.style, attr):
            value = getattr(element.style, attr)
            return self._safe_float(value) if value is not None else None
        return None

    def _get_volume(self, element: Any) -> Optional[float]:
        """安全地获取音量值"""
        if hasattr(element, 'volume') and hasattr(element.volume, 'velocity'):
            return self._safe_float(element.volume.velocity)
        return None

    def _format_measure_notes(self, measure: stream.Measure) -> List[Dict[str, Any]]:
        """格式化MusicXML小节数据以便比较"""
        result = []
        for element in measure.notesAndRests:
            base_data = {
                'duration': self._safe_float(element.duration.quarterLength),
                'x': self._get_style_value(element, 'absoluteX'),
                'y': self._get_style_value(element, 'absoluteY'),
                'dynamics': self._get_volume(element)
            }

            if isinstance(element, note.Rest):
                note_data = {
                    **base_data,
                    'pitch': 'rest',
                    'is_rest': True,
                    'is_chord': False
                }
            elif isinstance(element, chord.Chord):
                note_data = {
                    **base_data,
                    'pitch': [p.nameWithOctave for p in element.pitches],
                    'is_rest': False,
                    'is_chord': True
                }
            else:  # 单个音符
                note_data = {
                    **base_data,
                    'pitch': element.nameWithOctave,
                    'is_rest': False,
                    'is_chord': False
                }

            result.append(note_data)
        return result

    def _format_original_notes(self, notes: List[Note]) -> List[Dict[str, Any]]:
        """格式化原始音符数据以便比较"""
        notes_by_x = defaultdict(list)
        for note in notes:
            notes_by_x[self._safe_float(note.x)].append(note)

        result = []
        for x, note_group in sorted(notes_by_x.items()):
            if len(note_group) > 1:  # 和弦
                note_data = {
                    'pitch': [n.pitch_name for n in note_group],
                    'duration': self._safe_float(note_group[0].duration_beats),
                    'x': self._safe_float(x),
                    'y': self._safe_float(sum(n.y for n in note_group) / len(note_group)),
                    'is_rest': False,
                    'is_chord': True,
                    'dynamics': self._safe_float(sum(n.dynamics for n in note_group) / len(note_group))
                }
            else:  # 单个音符
                note = note_group[0]
                note_data = {
                    'pitch': note.pitch_name,
                    'duration': self._safe_float(note.duration_beats),
                    'x': self._safe_float(note.x),
                    'y': self._safe_float(note.y),
                    'is_rest': note.is_rest,
                    'is_chord': False,
                    'dynamics': self._safe_float(note.dynamics)
                }
            result.append(note_data)

        return result

    def _ensure_json_serializable(self, obj: Any) -> Any:
        """确保对象是JSON可序列化的"""
        if isinstance(obj, dict):
            return {k: self._ensure_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._ensure_json_serializable(v) for v in obj]
        elif isinstance(obj, Fraction):
            return float(obj)
        elif isinstance(obj, float) or isinstance(obj, int):
            return obj
        else:
            return obj

def convert_json_to_musicxml(json_file: str, output_file: str, debug_measures: Optional[List[int]] = None):
    """将JSON转换为MusicXML"""
    try:
        # 读取JSON文件
        with open(json_file, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        # 解析JSON数据为 ScoreData 对象
        score_data = ScoreData.from_dict(json_data)
        
        # 创建Score对象
        score = Score(
            measures=[Measure(number=i+1, notes=m.notes) 
                     for i, m in enumerate(score_data.measures)],
            time_beats=score_data.timeBeats,
            time_beat_type=score_data.timeBeatType
        )
        
        # 创建MusicXML生成器并生成文件
        generator = MusicXMLGenerator(score, score_data)  # 传入 score_data
        score_obj = generator.generate(debug_measures=debug_measures)
        
        # 写入MusicXML文件
        score_obj.write('musicxml', output_file)
        print(f"Successfully converted to {output_file}")
        
    except Exception as e:
        print(f"Error during conversion: {str(e)}")
        traceback.print_exc()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Convert JSON to MusicXML')
    parser.add_argument('input_file', help='Input JSON file')
    parser.add_argument('output_file', help='Output MusicXML file')
    parser.add_argument('--debug-measure', help='Measure number to debug', type=str)
    
    args = parser.parse_args()
    
    # 处理调试小节参数
    debug_measures = None
    if args.debug_measure:
        debug_measures = [int(m) for m in args.debug_measure.split(',')]
    
    convert_json_to_musicxml(args.input_file, args.output_file, debug_measures)