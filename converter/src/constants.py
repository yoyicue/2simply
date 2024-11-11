# constants.py
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Tuple, Union
import music21
from src.duration import DurationManager, DurationInfo

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
    NORMAL = "normal"      # 普通音符
    REST = "rest"         # 休止符
    CHORD = "chord"       # 和弦
    GRACE = "grace"       # 装饰音

@dataclass
class Position:
    """位置信息"""
    x: float  # X坐标
    y: float  # Y坐标
    beats: float  # 拍位置
    
    @property
    def staff(self) -> ClefType:
        """根据Y坐标确定所属谱表"""
        return ClefType.TREBLE if self.y >= STAFF_SPLIT_Y else ClefType.BASS

@dataclass 
class Note:
    """音符数据模型"""
    pitch_name: str
    duration_beats: float
    position: Position
    duration_type: str
    
    @classmethod
    def from_json(cls, note_data: dict) -> 'Note':
        """从JSON数据创建Note实例"""
        try:
            position = Position(
                x=float(note_data['x']),
                y=float(note_data['y']),
                beats=float(note_data['positionBeats'])
            )
            
            return cls(
                pitch_name=note_data['pitchName'],
                duration_beats=float(note_data['durationBeats']),
                position=position,
                duration_type=note_data['durationType']
            )
        except Exception as e:
            print(f"Error creating Note from JSON: {str(e)}")
            raise
    
    @property
    def staff(self) -> ClefType:
        """获取音符所属谱表"""
        return self.position.staff
    
    @property
    def x(self) -> float:
        return self.position.x
        
    @property
    def y(self) -> float:
        return self.position.y
        
    @property
    def position_beats(self) -> float:
        return self.position.beats
    
    def to_music21(self) -> music21.note.Note:
        """转换为music21音符"""
        note = music21.note.Note(self.pitch_name)
        note.duration = music21.duration.Duration(self.duration_beats)
        return note
    
    def get_end_position(self) -> float:
        """获取音符结束位置"""
        return self.position_beats + self.duration_beats
    
    def get_duration_info(self) -> DurationInfo:
        """获取音符的时值信息"""
        return DurationManager.BASE_DURATIONS.get(
            self.duration_type, 
            DurationManager.BASE_DURATIONS["quarter"]  # 默认使用四分音符
        )

@dataclass
class Measure:
    """小节数据模型"""
    number: int
    notes: List[Note]
    start_position: float
    
    def get_notes_by_staff(self, clef_type: ClefType) -> List[Note]:
        """根据谱号获取音符列表"""
        return [
            note for note in self.notes
            if (clef_type == ClefType.TREBLE and note.staff == ClefType.TREBLE) or
               (clef_type == ClefType.BASS and note.staff == ClefType.BASS)
        ]
    
    def get_measure_start_beat(self) -> float:
        """获取小节起始拍位置"""
        return (self.number - 1) * BEATS_PER_MEASURE
    
    def validate_duration(self) -> Tuple[bool, float]:
        """验证小节时值"""
        music21_elements = [note.to_music21() for note in self.notes]
        return DurationManager.validate_measure_duration(
            music21_elements, 
            BEATS_PER_MEASURE
        )

@dataclass
class Score:
    """乐谱数据模型"""
    measures: List[Measure]
    
    @classmethod
    def from_json(cls, json_data: dict) -> 'Score':
        """从JSON创建Score实例"""
        measures = []
        print(f"Debug - measures count in JSON: {len(json_data.get('measures', []))}")
        
        for i, m_data in enumerate(json_data.get("measures", []), 1):
            try:
                notes = []
                for n_data in m_data.get("notes", []):
                    try:
                        note = Note.from_json(n_data)
                        notes.append(note)
                    except Exception as e:
                        print(f"Error processing note in measure {i}: {str(e)}")
                        continue
                
                measure = Measure(
                    number=i,
                    notes=sorted(notes, key=lambda n: n.x),
                    start_position=float(m_data.get("startPositionBeats", 0))
                )
                measures.append(measure)
                print(f"Debug - Processed measure {i} with {len(notes)} notes")
            except Exception as e:
                print(f"Error processing measure {i}: {str(e)}")
                continue
        
        score = cls(measures=measures)
        print(f"Debug - Created Score with {len(score.measures)} measures")
        return score