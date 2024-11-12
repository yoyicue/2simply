from dataclasses import dataclass
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
    # 必需参数（无默认值）
    pitch_name: str
    duration_beats: float
    duration_seconds: float
    duration_type: str
    position_beats: float
    position_seconds: float
    
    # 可选参数（有默认值）
    staff: Optional[str] = None
    width: float = 0.0
    x: float = 0.0
    y: float = 0.0
    dots: int = 0
    pitch_midi_note: Optional[int] = None
    tie_type: Optional[str] = None

    @classmethod
    def from_json(cls, note_data: dict) -> 'Note':
        """从JSON数据创建Note实例"""
        y = note_data.get('y', 0.0)
        # 根据y坐标确定所属谱表
        staff = ClefType.TREBLE.value if y > STAFF_SPLIT_Y else ClefType.BASS.value
        
        return cls(
            staff=staff,  # 设置 staff 属性
            pitch_name=note_data['pitchName'],
            duration_beats=note_data['durationBeats'],
            duration_seconds=note_data['durationSeconds'],
            duration_type=note_data['durationType'],
            position_beats=note_data['positionBeats'],
            position_seconds=note_data['positionSeconds'],
            width=note_data.get('width', 0.0),
            x=note_data.get('x', 0.0),
            y=y,
            dots=note_data.get('dots', 0),
            pitch_midi_note=note_data.get('pitchMidiNote'),
            tie_type=note_data.get('tieType')
        )

@dataclass
class Measure:
    """小节数据模型"""
    number: int
    height: float
    staff_distance: float
    width: float
    x: float
    y: float
    start_position_beats: float
    start_position_seconds: float
    notes: List[Note]

    @classmethod
    def from_json(cls, measure_data: dict) -> 'Measure':
        """从JSON数据创建Measure实例"""
        return cls(
            number=measure_data.get('number', 0) + 1,
            height=measure_data['height'],
            staff_distance=measure_data['staffDistance'],
            width=measure_data['width'],
            x=measure_data['x'],
            y=measure_data['y'],
            start_position_beats=measure_data['startPositionBeats'],
            start_position_seconds=measure_data['startPositionSeconds'],
            notes=[Note.from_json(note) for note in measure_data['notes']]
        )

    def get_notes_by_staff(self, clef_type: ClefType) -> List[Note]:
        """Return notes filtered by the specified clef type."""
        return [note for note in self.notes if note.staff == clef_type.value]

@dataclass
class Score:
    """乐谱数据模型"""
    measures: List[Measure]
    filename: Optional[str] = None  # 添加文件名属性
    tempo: int = TEMPO  # 添加速度属性
    tempo_text: str = TEMPO_TEXT  # 添加速度术语属性
    composer: str = COMPOSER  # 添加作者
    arranger: str = ARRANGER  # 添加编曲者
    lyricist: str = LYRICIST  # 添加作词者

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
    
    @classmethod
    def from_json(cls, json_path: str) -> 'Score':
        """从JSON文件创建Score对象"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            # 获取文件名（去除路径和扩展名）
            filename = json_path.split('/')[-1].rsplit('.json', 1)[0]
            
            # 获取速度和作者信息
            tempo = json_data.get('tempo', TEMPO)
            tempo_text = json_data.get('tempoText', TEMPO_TEXT)
            composer = json_data.get('composer', COMPOSER)
            arranger = json_data.get('arranger', ARRANGER)
            lyricist = json_data.get('lyricist', LYRICIST)
            
            measures_data = json_data.get('measures', [])
            print(f"Debug - measures count in JSON: {len(measures_data)}")
            
            measures = []
            for i, m in enumerate(measures_data):
                try:
                    # 使用原始小节号，如果没有则使用索引+1
                    measure_number = m.get('number', i + 1)
                    m['number'] = measure_number
                    measure = Measure.from_json(m)
                    measures.append(measure)
                    if i == 0:  # 只打印第一个小节的数据
                        print(f"Debug - First measure data: {m}")
                except Exception as e:
                    print(f"Debug - Error processing measure {i+1}: {str(e)}")
                    raise
            
            if not measures:
                raise ValueError("JSON文件中没有小节数据")
            
            # 验证小节号的连续性
            measure_numbers = [m.number for m in measures]
            expected_numbers = list(range(1, len(measures) + 1))
            if measure_numbers != expected_numbers:
                print(f"Warning: Measure numbers are not sequential. Found: {measure_numbers}")
                # 重新编号小节
                for i, measure in enumerate(measures, start=1):
                    measure.number = i
            
            print(f"Debug - Successfully loaded {len(measures)} measures")
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