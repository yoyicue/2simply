from dataclasses import dataclass, asdict
from enum import Enum
from typing import List, Optional
import music21
import json

# 全局常量
TIME_SIGNATURE = "4/4"  
KEY_SIGNATURE = "C"
TOTAL_MEASURES = 17
STAFF_SPLIT_Y = -60
BEATS_PER_MEASURE = 4.0

# 添加速度相关常量
TEMPO = 132  # BPM (每分钟节拍数)
TEMPO_TEXT = ""  # 速度术语

# 添加作者相关常量
COMPOSER = " "  # 默认作者名
ARRANGER = ""  # 编曲者
LYRICIST = ""  # 作词者

# MIDI timing constants
TICKS_PER_QUARTER_NOTE = 10080  # MIDI ticks per quarter note
DURATION_SCALE_FACTOR = 0.5     # Scale factor to convert to output duration (1/8)
DURATION_BEATS_PRECISION = 3     # Decimal places for duration in beats
DURATION_SECONDS_PRECISION = 8   # Decimal places for duration in seconds
MIN_DURATION_BEATS = 0.25       # Minimum duration in beats (eighth note)

class ClefType(Enum):
    """谱号类型"""
    TREBLE = "treble"  # 高音谱号
    BASS = "bass"      # 低音谱号

class NoteType(Enum):
    """音符类型"""
    NORMAL = "normal"  # 普通音符
    REST = "rest"      # 休止符
    CHORD = "chord"    # 和弦
    GRACE = "grace"    # 装饰音

@dataclass
class Position:
    """位置信息"""
    x: float
    y: float
    beats: float

@dataclass
class Note:
    """音符数据模型"""
    # snake_case参数（必需）
    pitch_name: str
    duration_beats: float
    duration_seconds: float
    duration_type: str
    position_beats: float
    position_seconds: float
    width: float
    height: float
    x: float
    y: float
    staff: str  # 添加 staff 属性
    dots: int = 0
    pitch_midi_note: Optional[int] = None
    tie_type: Optional[str] = None
    is_chord: bool = False
    is_tuplet: bool = False
    tuplet_ratio: Optional[str] = None
    accidental: Optional[str] = None  # 升降号
    accidental_cautionary: bool = False  # 是否是提示性升降号

    def __post_init__(self):
        """在初始化后处理参数"""
        # 验证必需参数
        if not all([
            self.pitch_name,
            self.duration_beats is not None,
            self.duration_seconds is not None,
            self.duration_type,
            self.position_beats is not None,
            self.position_seconds is not None,
            self.staff  # 添加 staff 验证
        ]):
            raise ValueError("Missing required parameters for Note")

    # 添加 staff 的 getter 方法
    def get_staff(self) -> str:
        return self.staff

    # 改用方法而不是property
    def get_pitch_name(self) -> str:
        return self.pitch_name

    def get_duration_beats(self) -> float:
        return self.duration_beats

    def get_duration_seconds(self) -> float:
        return self.duration_seconds

    def get_duration_type(self) -> str:
        return self.duration_type

    def get_position_beats(self) -> float:
        return self.position_beats

    def get_position_seconds(self) -> float:
        return self.position_seconds

    def get_pitch_midi_note(self) -> Optional[int]:
        return self.pitch_midi_note

    def get_tie_type(self) -> Optional[str]:
        return self.tie_type

    # 为了JSON序列化，提供camelCase属性
    @property
    def pitchName(self) -> str:
        return self.pitch_name

    @property
    def durationBeats(self) -> float:
        return self.duration_beats

    @property
    def durationSeconds(self) -> float:
        return self.duration_seconds

    @property
    def durationType(self) -> str:
        return self.duration_type

    @property
    def positionBeats(self) -> float:
        return self.position_beats

    @property
    def positionSeconds(self) -> float:
        return self.position_seconds

    @property
    def pitchMidiNote(self) -> Optional[int]:
        return self.pitch_midi_note

    @property
    def tieType(self) -> Optional[str]:
        return self.tie_type

    def is_chord_note(self) -> bool:
        return self.is_chord

    @classmethod
    def from_json(cls, note_data: dict) -> 'Note':
        """从JSON数据创建Note实例，支持两种命名风格"""
        # 创建命名风格映射
        field_mapping = {
            'pitch_name': ['pitch_name', 'pitchName'],
            'duration_beats': ['duration_beats', 'durationBeats'],
            'duration_seconds': ['duration_seconds', 'durationSeconds'],
            'duration_type': ['duration_type', 'durationType'],
            'position_beats': ['position_beats', 'positionBeats'],
            'position_seconds': ['position_seconds', 'positionSeconds'],
            'pitch_midi_note': ['pitch_midi_note', 'pitchMidiNote'],
            'tie_type': ['tie_type', 'tieType'],
            'accidental': ['accidental', 'accidentalType'],
            'accidental_cautionary': ['accidental_cautionary', 'accidentalCautionary']
        }

        # 获取数据，支持两种命名风格
        def get_value(field_names):
            for name in field_names:
                if name in note_data:
                    return note_data[name]
            return None

        y = note_data.get('y', 0.0)
        # 根据y坐标确定所属谱表
        staff = ClefType.TREBLE.value if y > STAFF_SPLIT_Y else ClefType.BASS.value

        # 增加chord属性解析
        is_chord = note_data.get('is_chord', False)

        # 创建Note实例时只使用snake_case参数名
        return cls(
            staff=staff,  # 包含 staff 参数
            pitch_name=get_value(field_mapping['pitch_name']),
            duration_beats=get_value(field_mapping['duration_beats']),
            duration_seconds=get_value(field_mapping['duration_seconds']),
            duration_type=get_value(field_mapping['duration_type']),
            position_beats=get_value(field_mapping['position_beats']),
            position_seconds=get_value(field_mapping['position_seconds']),
            width=note_data.get('width', 0.0),
            height=note_data.get('height', 0.0),
            x=note_data.get('x', 0.0),
            y=y,
            dots=note_data.get('dots', 0),
            pitch_midi_note=get_value(field_mapping['pitch_midi_note']),
            tie_type=get_value(field_mapping['tie_type']),
            is_chord=is_chord,
            accidental=get_value(field_mapping['accidental']),
            accidental_cautionary=get_value(field_mapping['accidental_cautionary'])
        )

    def to_dict(self) -> dict:
        """转换为字典"""
        return asdict(self)

@dataclass
class Measure:
    """小节数据模型"""
    # 必需参数
    number: int
    height: float
    staff_distance: float
    width: float
    x: float
    y: float
    start_position_beats: float
    start_position_seconds: float
    notes: List[Note]

    def __post_init__(self):
        """在初始化后处理参数"""
        # 验证必需参数
        if not all([
            self.staff_distance is not None,
            self.start_position_beats is not None,
            self.start_position_seconds is not None
        ]):
            raise ValueError("Missing required parameters for Measure")

    # 为JSON序列化提供camelCase getter
    @property
    def staffDistance(self) -> float:
        return self.staff_distance

    @property
    def startPositionBeats(self) -> float:
        return self.start_position_beats

    @property
    def startPositionSeconds(self) -> float:
        return self.start_position_seconds

    @classmethod
    def from_json(cls, measure_data: dict) -> 'Measure':
        """从JSON数据创建Measure实例，支持两种命名风格"""
        # 首先转换所有可能的camelCase键为snake_case
        converted_data = {}
        
        # 基本字段的直接映射
        direct_fields = ['number', 'height', 'width', 'x', 'y']
        for field in direct_fields:
            if field in measure_data:
                converted_data[field] = measure_data[field]
            elif field.lower() in measure_data:  # 处理可能的大小写差异
                converted_data[field] = measure_data[field.lower()]

        # 特殊字段的映射
        field_mapping = {
            'staff_distance': ['staff_distance', 'staffDistance'],
            'start_position_beats': ['start_position_beats', 'startPositionBeats'],
            'start_position_seconds': ['start_position_seconds', 'startPositionSeconds']
        }

        # 获取数据，支持两种命名风格
        for snake_case, variants in field_mapping.items():
            for variant in variants:
                if variant in measure_data:
                    converted_data[snake_case] = measure_data[variant]
                    break

        # 处理notes数组
        if 'notes' in measure_data:
            converted_data['notes'] = [Note.from_json(note) for note in measure_data['notes']]

        # 使用转换后的数据创建实例
        return cls(
            number=converted_data.get('number'),
            height=converted_data.get('height'),
            staff_distance=converted_data.get('staff_distance'),
            width=converted_data.get('width'),
            x=converted_data.get('x'),
            y=converted_data.get('y'),
            start_position_beats=converted_data.get('start_position_beats'),
            start_position_seconds=converted_data.get('start_position_seconds'),
            notes=converted_data.get('notes', [])
        )

    def get_notes_by_staff(self, clef_type: ClefType) -> List[Note]:
        """Return notes filtered by the specified clef type."""
        return [note for note in self.notes if note.staff == clef_type.value]

    def to_dict(self) -> dict:
        """转换为字典"""
        data = asdict(self)
        data['notes'] = [note.to_dict() for note in self.notes]
        return data

@dataclass
class Score:
    """乐谱数据模型"""
    measures: List[Measure]
    
    # snake_case参数
    filename: Optional[str] = None
    tempo: int = TEMPO
    tempo_text: str = TEMPO_TEXT
    composer: str = COMPOSER
    arranger: str = ARRANGER
    lyricist: str = LYRICIST
    _time_signature: str = TIME_SIGNATURE  # 私有变量存储拍号

    def __post_init__(self):
        """在初始化后处理参数"""
        if not self.measures:
            raise ValueError("Score must have at least one measure")
        # 检测并设置拍号
        self._time_signature = self.get_time_signature()

    @property
    def time_signature(self) -> str:
        """获取拍号"""
        return self._time_signature

    def get_time_signature(self) -> str:
        """动态检测拍号
        
        通过分析相邻小节的起始位置差值来确定每小节的拍数，
        通过分析第一个小节中音符的最短时值来确定拍号分母。
        
        Returns:
            str: 检测到的拍号，格式为"分子/分母"，默认为"4/4"
        """
        if len(self.measures) < 2:
            return TIME_SIGNATURE  # 如果只有一个小节，返回默认拍号
            
        # 获取每小节拍数（从相邻小节起始位置差值得到）
        beats_per_measure = self.measures[1].start_position_beats - self.measures[0].start_position_beats
        
        # 分析第一个小节的音符时值
        first_measure = self.measures[0]
        if not first_measure.notes:
            return TIME_SIGNATURE  # 如果第一个小节没有音符，返回默认拍号
            
        # 默认使用4作为分母（四分音符为一拍）
        denominator = 4
        
        # 计算分子，保持总拍数不变
        numerator = int(beats_per_measure * (denominator / 4))
        
        return f"{numerator}/{denominator}"

    def add_metadata_to_score(self, score: music21.stream.Score) -> None:
        """向乐谱添加元数据（包括标题、作者等）"""
        if not score.metadata:
            score.metadata = music21.metadata.Metadata()
        
        # 设置标题
        if self.filename:
            score.metadata.movementName = self.filename
        
        # 设置作者信息
        if self.composer:
            score.metadata.composer = self.composer
        if self.arranger:
            score.metadata.arranger = self.arranger
        if self.lyricist:
            score.metadata.lyricist = self.lyricist

    def add_tempo_to_score(self, score: music21.stream.Score) -> None:
        """向乐谱添加速度标记"""
        mm = music21.tempo.MetronomeMark(number=self.tempo, text=self.tempo_text)
        first_measure = score.parts[0].measure(1)
        if first_measure:
            first_measure.insert(0, mm)

    # 为JSON序列化提供camelCase getter
    @property
    def fileName(self) -> Optional[str]:
        return self.filename

    @property
    def tempoText(self) -> str:
        return self.tempo_text

    @classmethod
    def from_json(cls, json_path: str, debug_enabled: bool = False) -> 'Score':
        """从JSON文件创建Score对象"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            # 获取文件名（去除路径和扩展名）
            filename = json_path.split('/')[-1].rsplit('.json', 1)[0]
            
            # 创建命名风格映射
            field_mapping = {
                'tempo_text': ['tempo_text', 'tempoText'],
                'filename': ['filename', 'fileName']
            }

            def get_value(field_names):
                for name in field_names:
                    if name in json_data:
                        return json_data[name]
                return None
            
            # 获取速度和作者信息
            tempo = json_data.get('tempo', TEMPO)
            tempo_text = get_value(field_mapping['tempo_text']) or TEMPO_TEXT
            composer = json_data.get('composer', COMPOSER)
            arranger = json_data.get('arranger', ARRANGER)
            lyricist = json_data.get('lyricist', LYRICIST)
            
            measures_data = json_data.get('measures', [])
            if debug_enabled:
                print(f"Debug - measures count in JSON: {len(measures_data)}")
            
            measures = []
            for i, m in enumerate(measures_data):
                try:
                    measure_number = m.get('number', i + 1)
                    m['number'] = measure_number
                    measure = Measure.from_json(m)
                    measures.append(measure)
                    if debug_enabled and i == 0:
                        print(f"Debug - First measure data: {m}")
                except Exception as e:
                    print(f"Debug - Error processing measure {i+1}: {str(e)}")
                    raise
            
            if not measures:
                raise ValueError("JSON文件中没有小节数据")
            
            return cls(
                measures=measures, 
                filename=filename,
                tempo=tempo,
                tempo_text=tempo_text,
                composer=composer,
                arranger=arranger,
                lyricist=lyricist
            )
            
        except FileNotFoundError:
            raise FileNotFoundError(f"找不到JSON文件：{json_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON文件格式错误：{str(e)}")
        except Exception as e:
            raise Exception(f"解析JSON文件时出错：{str(e)}")

    def to_dict(self) -> dict:
        """转换为字典"""
        data = asdict(self)
        data['measures'] = [measure.to_dict() for measure in self.measures]
        return data

    def save_json(self, output_path: str) -> None:
        """保存为JSON文件
        
        Args:
            output_path: 输出文件路径
            
        Raises:
            IOError: 文件写入失败
        """
        try:
            # 转换为字典
            data = self.to_dict()
            
            # 写入JSON文件
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            raise IOError(f"保存JSON文件失败: {str(e)}")