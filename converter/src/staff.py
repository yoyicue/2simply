# src/staff.py
from dataclasses import dataclass
from typing import List, Optional
import music21
from src.constants import Note, ClefType, DurationManager

@dataclass
class GridSlot:
    """网格槽位"""
    position: float  # 开始位置(拍)
    duration: float  # 持续时间(拍)
    note: Optional[Note] = None  # 音符
    is_rest: bool = True  # 是否是休止符

class StaffProcessor:
    """谱表处理器"""
    GRID_RESOLUTION = 0.25  # 网格分辨率(拍)
    MEASURE_LENGTH = 4.0   # 小节长度(拍)
    
    def __init__(self, clef_type: ClefType):
        self.clef_type = clef_type
        self.grid: List[GridSlot] = []
        self._init_grid()
        self.has_notes = False  # 标记是否包含实际音符
    
    def _init_grid(self):
        """初始化网格"""
        slots = int(self.MEASURE_LENGTH / self.GRID_RESOLUTION)
        self.grid = [
            GridSlot(
                position=i * self.GRID_RESOLUTION,
                duration=self.GRID_RESOLUTION
            ) for i in range(slots)
        ]
    
    def place_note(self, note: Note):
        """在网格中放置音符"""
        self.has_notes = True
        start_slot = int(note.position_beats / self.GRID_RESOLUTION)
        duration_slots = int(note.duration_beats / self.GRID_RESOLUTION)
        
        merged_slot = GridSlot(
            position=note.position_beats,  # 使用实际位置
            duration=note.duration_beats,  # 使用实际时值
            note=note,
            is_rest=False
        )
        
        self.grid[start_slot:start_slot + duration_slots] = [merged_slot] * duration_slots
    
    def get_music21_elements(self) -> List[music21.base.Music21Object]:
        """获取所有music21元素(音符和休止符)"""
        if not self.has_notes:
            rest = music21.note.Rest(quarterLength=self.MEASURE_LENGTH)
            return [rest]
            
        elements = []
        current_position = 0.0
        
        # 按位置排序的音符槽
        note_slots = sorted(
            [slot for slot in self.grid if not slot.is_rest and slot.note is not None],
            key=lambda slot: (slot.position, slot.note.x)  # 使用x坐标作为次要排序
        )
        
        # 处理每个音符位置
        for slot in note_slots:
            # 添加之前的休止符
            if slot.position > current_position:
                rest_duration = slot.position - current_position
                if rest_duration > 0:
                    rest = music21.note.Rest(quarterLength=rest_duration)
                    elements.append(rest)
            
            # 创建音符
            note = slot.note.to_music21()
            note.quarterLength = slot.note.duration_beats
            elements.append(note)
            
            current_position = slot.position + slot.note.duration_beats
        
        # 添加最后的休止符
        if current_position < self.MEASURE_LENGTH:
            rest = music21.note.Rest(quarterLength=self.MEASURE_LENGTH - current_position)
            elements.append(rest)
            
        return elements

class MeasureProcessor:
    """小节处理器"""
    
    def __init__(self, measure_number: int):
        self.measure_number = measure_number
        self.treble_staff = StaffProcessor(ClefType.TREBLE)
        self.bass_staff = StaffProcessor(ClefType.BASS)
        
    def process_notes(self, notes: List[Note]):
        """处理小节中的所有音符"""
        # 按照位置和原始顺序排序音符
        sorted_notes = sorted(notes, key=lambda n: (n.position_beats, notes.index(n)))
        
        for note in sorted_notes:
            if note.y < -60:  # 高音谱表
                self.treble_staff.place_note(note)
            else:  # 低音谱表
                self.bass_staff.place_note(note)
    
    def create_music21_measure(self) -> music21.stream.Measure:
        """创建music21小节对象"""
        measure = music21.stream.Measure(number=self.measure_number)
        
        # 创建高音谱表声部
        treble_voice = music21.stream.Voice()
        for i, element in enumerate(self.treble_staff.get_music21_elements()):
            treble_voice.insertAndShift(i, element)
        
        # 创建低音谱表声部
        bass_voice = music21.stream.Voice()
        for i, element in enumerate(self.bass_staff.get_music21_elements()):
            bass_voice.insertAndShift(i, element)
        
        # 将声部添加到小节中
        measure.insert(0, treble_voice)
        measure.insert(0, bass_voice)
        
        return measure
        
    def get_all_elements(self) -> List[music21.base.Music21Object]:
        """获取所有音乐元素用于调试"""
        elements = []
        # 获取高音谱表元素
        elements.extend(self.treble_staff.get_music21_elements())
        # 获取低音谱表元素
        elements.extend(self.bass_staff.get_music21_elements())
        return elements