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

    @classmethod
    def from_json(cls, json_path: str) -> 'Score':
        """从JSON文件创建Score对象"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
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
            return cls(measures)
            
        except FileNotFoundError:
            raise FileNotFoundError(f"找不到JSON文件：{json_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON文件格式错误：{str(e)}")
        except Exception as e:
            raise Exception(f"解析JSON文件时出错：{str(e)}")