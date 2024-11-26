import os
from typing import List, Dict, Optional, Tuple, Union
import music21
from music21.exceptions21 import Music21Exception
import xml.etree.ElementTree as ET
from src.debug import ScoreDebugger, logger
from src.constants import (
    Note, Score, ClefType, Measure,
    STAFF_SPLIT_Y, BEATS_PER_MEASURE, DURATION_SCALE_FACTOR
)
from src.duration import DurationManager, DurationInfo
import json
import random

class XMLConverterError(Exception):
    """XML转换器基础异常类"""
    pass

class XMLFileError(XMLConverterError):
    """XML文件相关错误"""
    pass

class XMLFormatError(XMLConverterError):
    """XML格式错误"""
    pass

class MusicStructureError(XMLConverterError):
    """音乐结构错误"""
    pass

class MusicXMLConverter:
    """MusicXML to JSON 转换器"""
    
    REQUIRED_ELEMENTS = [
        'part',           # 声部
        'measure',        # 小节
        'attributes',     # 属性（如谱号、拍号等）
        'note'           # 音符
    ]
    
    BASE_X = 71.6765  # 基准起始位置
    BEAT_SPACING = 57.95  # 每拍基准间距
    FIRST_MEASURE_X = 71.6765  # 第一小节的起始x坐标
    
    def __init__(self, xml_path: str, debugger: Optional[ScoreDebugger] = None):
        """
        初始化XML转换器
        
        Args:
            xml_path: MusicXML文件路径
            debugger: 可选的调试器实例
            
        Raises:
            XMLFileError: 文件不存在或无法访问
            XMLFormatError: XML格式错误
            MusicStructureError: 音乐结构无效
            XMLConverterError: 其他转换相关错误
        """
        self.xml_path = xml_path
        self.debugger = debugger
        self.debug_measures = set()
        # 添加小节位置跟踪
        self._previous_measure_x = 71.6765
        self._previous_measure_width = self.BEAT_SPACING * BEATS_PER_MEASURE
        self._measure_start_positions = {1: self.FIRST_MEASURE_X}
        
        # 验证文件
        self._validate_file()
        
        try:
            # 尝试解析XML文件
            self.score = music21.converter.parse(xml_path)
            
            # 基本验证
            self._validate_score_structure()
            
            # 初始化调试信息
            self._init_debug_info()
            
            # 初始化转换状态
            self.tie_tracks = {}
            self._current_measure_debug = None
            
        except Music21Exception as e:
            error_msg = f"解析MusicXML文件时出错: {str(e)}"
            logger.error(error_msg)
            raise XMLFormatError(error_msg)
        except Exception as e:
            error_msg = f"初始化转换器时出错: {str(e)}"
            logger.error(error_msg)
            raise XMLConverterError(error_msg)
            
    def _validate_file(self):
        """
        验证XML文件的存在性和基本格式
        
        Raises:
            XMLFileError: 文件验证失败
        """
        # 检查文件是否存在
        if not os.path.exists(self.xml_path):
            error_msg = f"找不到XML文件: {self.xml_path}"
            logger.error(error_msg)
            raise XMLFileError(error_msg)
            
        # 检查文件扩展名
        if not self.xml_path.lower().endswith(('.xml', '.musicxml')):
            error_msg = f"不支持的文件格式: {self.xml_path}"
            logger.warning(error_msg)
            
        # 尝试解析XML结构
        try:
            tree = ET.parse(self.xml_path)
            root = tree.getroot()
            
            # 检查是否为MusicXML文件
            if 'score-partwise' not in root.tag:
                error_msg = "文件不是有效的MusicXML文件"
                logger.error(error_msg)
                raise XMLFormatError(error_msg)
                
        except ET.ParseError as e:
            error_msg = f"XML文件格式错误: {str(e)}"
            logger.error(error_msg)
            raise XMLFormatError(error_msg)
            
    def _validate_score_structure(self):
        """
        验证乐谱结构的有效性
        
        Raises:
            MusicStructureError: 乐谱结构验证失败
        """
        try:
            # 检查是否为有效的 Score 对象
            if not isinstance(self.score, music21.stream.Score):
                raise MusicStructureError("无法解析为有效的乐谱对象")
            
            # 获取所有声部
            parts = self.score.parts
            if not parts:
                raise MusicStructureError("乐谱中没有找到声部")
            
            # 检查声部数量（应该有两个声部：高音谱和低音谱）
            if len(parts) != 2:
                raise MusicStructureError(
                    f"乐谱必须包含两个声部(高音谱号和低音谱号), 当前包含 {len(parts)} 个声部"
                )
            
            # 检查每个声部的内容
            for part_index, part in enumerate(parts):
                part_name = f"部 {part_index + 1}"
                
                # 检查小节
                measures = part.getElementsByClass('Measure')
                if not measures:
                    raise MusicStructureError(f"{part_name} 中没有找到小节")
                
                # 检查第一个小节中的基本属性
                first_measure = measures[0]
                
                # 检查拍号
                time_signature = first_measure.timeSignature
                if not time_signature:
                    logger.warning(f"{part_name} 未指定拍号，将使用默认拍号")
                
                # 检查调号
                key_signature = first_measure.keySignature
                if not key_signature:
                    logger.warning(f"{part_name} 未指定调号，将使用默认调号")
                
                # 检查谱号
                clef = first_measure.clef
                if not clef:
                    logger.warning(f"{part_name} 未指定谱号，将使用默认谱号")
                
                # 检查是否包含音符或休止符
                notes = part.flatten().notesAndRests
                if not notes:
                    raise MusicStructureError(f"{part_name} 中没有找到音符或休止符")
            
            # 检查各声部的小节数是否一致
            measure_counts = [len(part.getElementsByClass('Measure')) for part in parts]
            if len(set(measure_counts)) > 1:
                raise MusicStructureError(
                    f"声部小数不一致: {', '.join(str(count) for count in measure_counts)}"
                )
            
            logger.info("乐谱结构验证通过")
            logger.debug(f"  声部数量: {len(parts)}")
            logger.debug(f"  小节数量: {measure_counts[0]}")
            
        except MusicStructureError:
            raise
        except Exception as e:
            raise MusicStructureError(f"验证乐谱结构时出错: {str(e)}")

    def _init_debug_info(self):
        """初始化调试信息"""
        if self.debugger:
            logger.info(f"初始化转换器 - 文件: {self.xml_path}")
            logger.info(f"调试小节: {self.debug_measures or '所有'}")
            
            try:
                # 记录基本乐谱信息
                parts = self.score.parts
                logger.debug("乐谱信息:")
                logger.debug(f"  声数量: {len(parts)}")
                logger.debug(f"  小节数量: {len(parts[0].getElementsByClass('Measure'))}")
                
                # 第个声部的基本属性
                first_measure = parts[0].getElementsByClass('Measure')[0]
                logger.debug("第一小节属性:")
                if first_measure.timeSignature:
                    logger.debug(f"  拍号: {first_measure.timeSignature}")
                if first_measure.keySignature:
                    logger.debug(f"  调号: {first_measure.keySignature}")
                if first_measure.clef:
                    logger.debug(f"  谱号: {first_measure.clef}")
                
                # 记录元数据
                if self.score.metadata:
                    logger.debug("元数据:")
                    if self.score.metadata.title:
                        logger.debug(f"  标题: {self.score.metadata.title}")
                    if self.score.metadata.composer:
                        logger.debug(f"  作者: {self.score.metadata.composer}")
                    
            except Exception as e:
                logger.warning(f"记录调试信息时出错: {str(e)}")

    def _iter_measures(self) -> List[Tuple[int, Tuple[music21.stream.Measure, music21.stream.Measure]]]:
        """遍历乐中的小节
        
        Returns:
            List[Tuple[int, Tuple[treble_measure, bass_measure]]]: 小节号和对应的高低音谱小节
        """
        try:
            # 获取高谱和低音谱
            parts = self.score.parts
            if len(parts) < 2:
                raise MusicStructureError("乐谱缺少双手声部")
            
            treble_part = parts[0]  # 高音谱
            bass_part = parts[1]    # 低音谱
            
            # 获取小节数量
            measure_count = len(treble_part.measures(1, None))
            
            # 遍历所有节
            measures = []
            for i in range(measure_count):
                measure_number = i + 1
                
                # 如果设置了调试小节，只处理指定的小节
                if self.debug_measures and measure_number not in self.debug_measures:
                    continue
                    
                # 获取对应小节
                treble_measure = treble_part.measure(measure_number)
                bass_measure = bass_part.measure(measure_number)
                
                if not treble_measure or not bass_measure:
                    logger.warning(f"小节 {measure_number} 不完整，跳过")
                    continue
                    
                measures.append((measure_number, (treble_measure, bass_measure)))
                
            return measures
            
        except Exception as e:
            error_msg = f"遍历小节时出错: {str(e)}"
            logger.error(error_msg)
            raise XMLConverterError(error_msg)

    def save_json(self, output_path: str) -> None:
        """保存为JSON文件
        
        Args:
            output_path: 输出文件路径
        """
        try:
            # 获取基础数结构
            data = self.convert()
            
            # 转为JSON格式的字典
            json_data = {
                'measures': [],
                'pageWidth': data['page_width']
            }
            
            # 转换measures
            for measure in data['measures']:
                json_data['measures'].append({
                    'number': measure.number,
                    'height': measure.height,
                    'notes': [{
                        'durationBeats': note.duration_beats,
                        'durationSeconds': note.duration_seconds,
                        'durationType': note.duration_type,
                        'height': note.height,
                        'pitchMidiNote': note.pitch_midi_note,
                        'pitchName': note.pitch_name,
                        'positionBeats': note.position_beats,
                        'positionSeconds': note.position_seconds,
                        'tieType': note.tie_type,
                        'width': note.width,
                        'x': note.x,
                        'y': note.y,
                        'staff': note.staff
                    } for note in measure.notes],
                    'staffDistance': measure.staff_distance,
                    'startPositionBeats': measure.start_position_beats,
                    'startPositionSeconds': measure.start_position_seconds,
                    'width': measure.width,
                    'x': measure.x,
                    'y': measure.y
                })
            
            # 写入JSON文件
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2)
                
        except Exception as e:
            error_msg = f"保存JSON文件失败: {str(e)}"
            logger.error(error_msg)
            raise XMLConverterError(error_msg)

    def _measure_to_dict(self, measure: Measure) -> dict:
        """将Measure对象转换为驼峰命名的字典"""
        return {
            'number': measure.number,
            'height': measure.height,
            'notes': [self._note_to_dict(n) for n in measure.notes],
            'staffDistance': measure.staff_distance,
            'startPositionBeats': measure.start_position_beats,
            'startPositionSeconds': measure.start_position_seconds,
            'width': measure.width,
            'x': measure.x,
            'y': measure.y
        }

    def _note_to_dict(self, note: Note) -> dict:
        """将Note对象转换为驼峰命名的字典"""
        return {
            'durationBeats': note.duration_beats,
            'durationSeconds': note.duration_seconds,
            'durationType': note.duration_type,
            'height': note.height,
            'pitchMidiNote': note.pitch_midi_note,
            'pitchName': note.pitch_name,
            'positionBeats': note.position_beats,
            'positionSeconds': note.position_seconds,
            'tieType': note.tie_type,
            'width': note.width,
            'x': note.x,
            'y': note.y,
            'staff': note.staff
        }

    def convert(self) -> dict:
        """执行转换并返回字典结构"""
        try:
            measures = []
            if self.debugger:
                logger.info("开始转换")
                if self.debug_measures:
                    logger.info("\n音符序列:")
            
            for measure_number, (treble_measure, bass_measure) in self._iter_measures():
                measure = self._convert_measure(measure_number, treble_measure, bass_measure)
                measures.append(measure)
                
                # 只在处理debug_measures中的小节时输出调试信息
                if self.debugger and measure_number in self.debug_measures:
                    logger.info(f"\n=== 小节 {measure_number} ===")
                    for note in measure.notes:
                        logger.info(f"- {note.pitch_name} ({note.duration_type}音符): "
                                  f"x={note.x:.2f}, y={note.y:.1f}, width={note.width:.1f}")
            
            # 返回完整的字典结构
            result = {
                'measures': measures,
                'page_width': 1069.55
            }
            
            if self.debugger:
                logger.info(f"\n转换完成 - 共处理 {len(measures)} 个小节")
            
            return result
            
        except Exception as e:
            error_msg = f"转换过程中出错: {str(e)}"
            logger.error(error_msg)
            raise XMLConverterError(error_msg)
        
    def _convert_to_camel_case(self, data: dict) -> dict:
        """将划线命名转换峰命名"""
        field_mapping = {
            'duration_beats': 'durationBeats',
            'duration_seconds': 'durationSeconds',
            'duration_type': 'durationType',
            'pitch_midi_note': 'pitchMidiNote',
            'pitch_name': 'pitchName',
            'position_beats': 'positionBeats',
            'position_seconds': 'positionSeconds',
            'tie_type': 'tieType',
            'start_position_beats': 'startPositionBeats',
            'start_position_seconds': 'startPositionSeconds',
            'staff_distance': 'staff_distance',
            'page_width': 'pageWidth',
            'number': 'number'
        }
        
        if isinstance(data, list):
            return [self._convert_to_camel_case(item if isinstance(item, dict) else item.__dict__)
                    for item in data]
        elif not isinstance(data, dict):
            return data
        
        result = {}
        for k, v in data.items():
            if isinstance(v, (list, dict)):
                v = self._convert_to_camel_case(v)
            new_key = field_mapping.get(k, k)
            result[new_key] = v
        return result
        
    def _calculate_y_position(self, pitch: music21.pitch.Pitch, clef_type: ClefType) -> float:
        """计算音符的Y坐标位置
        
        Args:
            pitch: 音符的音高
            clef_type: 谱号类型
            
        Returns:
            float: Y坐标位置
        """
        # 定义基准音高和位置
        if clef_type == ClefType.TREBLE:
            # 使用E4作为基准音，因为它在高音谱表第一线
            base_midi = 64  # E4
            base_y = -40.0  # E4的基准Y坐标
            semitone_spacing = 2.5  # 每个半音的间距
            
            # 计算与基准音高的半音差
            semitones = pitch.midi - base_midi
            
            # 使用非线性映射来更准确地匹配ground truth值
            if semitones > 0:
                # 对于高于E4的音符，稍微增加间距
                y = base_y + (semitones * 3.0)
            else:
                # 对于低于E4的音符，保持原有间距
                y = base_y + (semitones * 2.5)
        else:  # BASS
            # 使用G2作为基准音，因为它在低音谱表第一线
            base_midi = 43  # G2
            base_y = -155.74
            semitone_spacing = 2.5
            
            # 计算与基准音高的半音差
            semitones = pitch.midi - base_midi
            y = base_y + (semitones * semitone_spacing)
        
        return y
        
    def _convert_note(
        self,
        note: music21.note.Note,
        clef_type: ClefType,
        current_position: float,
        is_chord: bool = False,
        chord_index: int = 0
    ) -> Note:
        """转换单个音符
        
        Args:
            note: music21音符对象
            clef_type: 谱号类型
            current_position: 当前位置（以拍为单位）
            is_chord: 是否为和弦中的音符
            chord_index: 在和弦中的索引位置
            
        Returns:
            Note: 转换后的音符对象
        """
        # 检查是否为连音符组的一部分
        is_tuplet = False
        tuplet_ratio = None
        if hasattr(note, 'duration') and hasattr(note.duration, 'tuplets') and note.duration.tuplets:
            is_tuplet = True
            tuplet = note.duration.tuplets[0]  # 获取第一个连音符信息
            tuplet_ratio = f"{tuplet.numberNotesActual}:{tuplet.numberNotesNormal}"
        
        # 使用DurationManager获取时值信息
        dur_info, beats, seconds = DurationManager.extract_duration_info(note)
        
        # 如果是连音符，调整持续时间
        if is_tuplet:
            actual, normal = map(int, tuplet_ratio.split(':'))
            beats = beats * normal / actual
            seconds = seconds * normal / actual
        
        # 计算x坐标(考虑和弦位置)
        x = self._calculate_note_x_position(
            position_beats=current_position,
            measure_number=int(current_position / BEATS_PER_MEASURE) + 1,
            is_chord=is_chord,
            chord_index=chord_index
        )
        
        # 计算y坐标
        y = self._calculate_y_position(note.pitch, clef_type)
        
        # 创建音符对象
        note_obj = Note(
            pitch_name=note.nameWithOctave,
            duration_beats=beats,
            duration_seconds=seconds,
            duration_type=dur_info.type_name,
            position_beats=current_position,
            position_seconds=current_position * 60 / self._get_tempo(),
            width=10.0,
            height=10.0,
            x=x,
            y=y,
            staff=clef_type.value,
            pitch_midi_note=note.pitch.midi,
            tie_type=note.tie.type if note.tie else None,
            is_chord=is_chord
        )
        
        # 如果是连音符，添加连音符信息
        if is_tuplet:
            note_obj.is_tuplet = True
            note_obj.tuplet_ratio = tuplet_ratio
        
        return note_obj

    def _process_chord(
        self,
        chord: music21.chord.Chord,
        clef_type: ClefType,
        current_position: float
    ) -> List[Note]:
        """处理和弦"""
        notes = []
        for i, pitch in enumerate(chord.pitches):
            note = music21.note.Note(pitch, duration=chord.duration)
            notes.append(self._convert_note(
                note=note,
                clef_type=clef_type,
                current_position=current_position,
                is_chord=True,
                chord_index=i
            ))
        return notes

    def _convert_measure(
        self,
        measure_number: int,
        treble_measure: music21.stream.Measure,
        bass_measure: music21.stream.Measure
    ) -> Measure:
        """Convert a single measure with improved note handling"""
        try:
            start_position = (measure_number - 1) * BEATS_PER_MEASURE
            notes = []
            
            # 用于跟踪每个位置的和弦音符
            chord_positions = {}
            
            # 记录开始处理新的小节
            logger.debug(f"\nProcessing measure {measure_number}")
            logger.debug(f"Start position: {start_position}")
            
            # 处理高音谱和低音谱
            for measure, clef_type in [(treble_measure, ClefType.TREBLE), 
                                     (bass_measure, ClefType.BASS)]:
                try:
                    logger.debug(f"\nProcessing {clef_type.name} staff")
                    # 检查小节中的音符数量
                    note_count = len(list(measure.notesAndRests))
                    logger.debug(f"Found {note_count} notes/rests in {clef_type.name} staff")
                    
                    staff_notes = self._process_staff(
                        measure=measure,
                        clef_type=clef_type,
                        start_position=start_position,
                        chord_positions=chord_positions
                    )
                    
                    logger.debug(f"Processed {len(staff_notes)} notes in {clef_type.name} staff")
                    notes.extend(staff_notes)
                    
                except Exception as e:
                    logger.error(f"处理谱表出错 (clef={clef_type.value}): {str(e)}")
                    raise
            
            # 计算小节属性
            width = self._calculate_measure_width(notes)
            x = self._calculate_measure_x(measure_number)
            
            # 更新小节位置信息
            self._update_measure_positions(measure_number, width)
            
            # 输出调试信息
            if self.debugger:
                self._debug_measure_info(measure_number, notes, width, x)
            
            # 创建最终的小节对象
            measure = Measure(
                number=measure_number,
                height=200.0,
                staff_distance=85.0,
                width=width,
                x=x,
                y=-150.0,
                start_position_beats=start_position,
                start_position_seconds=start_position * 60 / self._get_tempo(),
                notes=sorted(notes, key=lambda n: (n.position_beats, n.y))
            )
            
            # 记录处理结果
            logger.debug(f"Measure {measure_number} processed:")
            logger.debug(f"- Width: {width}")
            logger.debug(f"- X position: {x}")
            logger.debug(f"- Total notes: {len(notes)}")
            
            return measure
            
        except Exception as e:
            logger.error(f"转换小节 {measure_number} 出: {str(e)}")
            logger.error(f"小节信息: treble={treble_measure}, bass={bass_measure}")
            raise XMLConverterError(f"转换小节 {measure_number} 失败: {str(e)}")

    def _process_staff(
        self,
        measure: music21.stream.Measure,
        clef_type: ClefType,
        start_position: float,
        chord_positions: Dict[float, float]
    ) -> List[Note]:
        """处理单个谱表的音符"""
        notes = []
        current_position = start_position
        
        for element in measure.notesAndRests:
            # 跳过休止符
            if isinstance(element, music21.note.Rest):
                current_position += element.quarterLength
                continue
            
            # 处理和弦
            if isinstance(element, music21.chord.Chord):
                chord_notes = self._process_chord(
                    chord=element,
                    clef_type=clef_type,
                    current_position=current_position
                )
                notes.extend(chord_notes)
            # 处理单个音符
            elif isinstance(element, music21.note.Note):
                note = self._convert_note(
                    note=element,
                    clef_type=clef_type,
                    current_position=current_position
                )
                notes.append(note)
                
            current_position += element.quarterLength
        
        return notes

    def _calculate_measure_width(self, notes: List[Note]) -> float:
        """计算小节宽度，使用更确的计算方法"""
        if not notes:
            return 150.0
        
        # 计算音符实际占用的宽度
        rightmost_x = max(note.x + note.width for note in notes)
        leftmost_x = min(note.x for note in notes)
        content_width = rightmost_x - leftmost_x
        
        # 添加边距
        left_margin = 20.0
        right_margin = 40.0
        
        # 根据音符密度和型调整宽度
        note_density = len(notes) / 4.0
        density_factor = min(1.2, max(1.0, note_density / 2.0))
        
        # 考音符类型的影响
        has_long_notes = any(note.duration_beats >= 2.0 for note in notes)
        type_factor = 1.1 if has_long_notes else 1.0
        
        width = (content_width + left_margin + right_margin) * density_factor * type_factor
        
        # 更新前一个小节的信息
        self._previous_measure_width = width
        
        return max(150.0, width)

    def _update_measure_positions(self, measure_number: int, width: float) -> None:
        """更新小节位置信息"""
        if measure_number == 1:
            self._previous_measure_x = 71.6765
        else:
            self._previous_measure_x = self._measure_start_positions[measure_number]
        
        next_x = self._previous_measure_x + width
        self._measure_start_positions[measure_number + 1] = next_x

    def _debug_measure_info(
        self,
        measure_number: int,
        notes: List[Note],
        width: float,
        x: float
    ) -> None:
        """增强的调试信息输出"""
        logger.info(f"\n=== 小节 {measure_number} ===")
        logger.info(f"小节起始位置: x={x:.2f}")
        logger.info(f"小节度: {width:.2f}")
        logger.info(f"音符数量: {len(notes)}")
        logger.info("音符列表:")
        
        for note in sorted(notes, key=lambda n: (n.position_beats, n.y)):
            relative_pos = note.position_beats - ((measure_number - 1) * BEATS_PER_MEASURE)
            logger.info(
                f"- {note.pitch_name} ({note.duration_type}音符): "
                f"x={note.x:.2f}, y={note.y:.1f}, "
                f"pos={note.position_beats:.1f} (相对位置: {relative_pos:.1f}), "
                f"{'[和弦]' if note.is_chord else ''}"
            )

    def _get_tempo(self) -> float:
        """获取速度"""
        for element in self.score.flatten().getElementsByClass(music21.tempo.MetronomeMark):
            return element.number
        return 120.0  # 默认速度
        
    def _get_tempo_text(self) -> str:
        """获取速度文字标记"""
        for element in self.score.flatten().getElementsByClass(music21.tempo.MetronomeMark):
            return element.text or ""
        return ""
        
    def _get_metadata_field(self, field: str) -> str:
        """获取元数据字段"""
        if self.score.metadata:
            return getattr(self.score.metadata, field, "") or ""
        return ""
        
    def _calculate_note_x_position(
        self,
        position_beats: float,
        measure_number: int,
        is_chord: bool = False,
        chord_index: int = 0
    ) -> float:
        """计算音符的X坐标位置"""
        # 获取小节起始位置
        if measure_number not in self._measure_start_positions:
            prev_measure = measure_number - 1
            prev_x = self._measure_start_positions.get(prev_measure, self.FIRST_MEASURE_X)
            prev_width = self._previous_measure_width or self.BEAT_SPACING * BEATS_PER_MEASURE
            self._measure_start_positions[measure_number] = prev_x + prev_width
        
        measure_x = self._measure_start_positions[measure_number]
        
        # 计算小节内的相对位置
        relative_pos = position_beats - ((measure_number - 1) * BEATS_PER_MEASURE)
        x = measure_x + self.BEAT_SPACING * relative_pos
        
        # 和弦音符的位置调整
        if is_chord:
            # 根据和弦中的位置调整x坐标
            x += chord_index * 5.0  # 每个和弦音符横向偏移5个单位
        
        return x

    def _calculate_measure_x(self, measure_number: int) -> float:
        """计算小节的X坐标"""
        if measure_number == 1:
            return self.FIRST_MEASURE_X
        return self._previous_measure_x + self._previous_measure_width

    def _create_note(
        self,
        note: music21.note.Note,
        duration_beats: float,
        duration_seconds: float,
        position_beats: float,
        x: float,
        clef_type: ClefType,
        is_chord: bool = False
    ) -> Note:
        """创建单个音符对象"""
        return Note(
            duration_beats=duration_beats,
            duration_seconds=duration_seconds,
            duration_type=note.duration.type,
            height=10.0,
            pitch_midi_note=note.pitch.midi,
            pitch_name=note.pitch.nameWithOctave,
            position_beats=position_beats,
            position_seconds=position_beats * 60 / self._get_tempo(),
            tie_type=note.tie.type if note.tie else None,
            width=10.0,
            x=x,
            y=self._calculate_y_position(note.pitch, clef_type),
            staff=clef_type.value,
            is_chord=is_chord
        )

    def _create_chord_note(
        self,
        pitch: music21.pitch.Pitch,
        duration_beats: float,
        duration_seconds: float,
        position_beats: float,
        x: float,
        clef_type: ClefType
    ) -> Note:
        """创建和弦中的音符对象
        
        使用DurationManager来处理时值，确保tuplet的正确表示。
        使用音高和谱号信息计算y坐标。
        """
        # 使用DurationManager获取tuplet的时值信息
        dur_info = DurationManager.get_duration_info('eighth')
        tuplet_duration = dur_info.quarter_length * DURATION_SCALE_FACTOR  # 0.5 * 0.25 = 0.125
        
        # 计算y坐标
        if clef_type == ClefType.TREBLE:
            base_midi = 69  # A4
            base_y = -40.0  # A4的基准y坐标
        else:  # BASS
            base_midi = 45  # A2
            base_y = -155.74  # A2的基准y坐标
        
        # 每个半音的垂直间距
        semitone_spacing = 5.0
        semitones = pitch.midi - base_midi
        y = base_y + (semitones * semitone_spacing)
        
        return Note(
            duration_beats=tuplet_duration,
            duration_seconds=duration_seconds,
            duration_type='eighth',
            height=10.0,
            pitch_midi_note=pitch.midi,
            pitch_name=pitch.nameWithOctave,
            position_beats=position_beats,
            position_seconds=position_beats * 60 / self._get_tempo(),
            tie_type=None,
            width=10.0,
            x=x,
            y=y,
            staff=clef_type.value,
            is_chord=True
        )

    @staticmethod
    def extract_duration_info(note: Union[music21.note.Note, music21.chord.Chord, music21.note.Rest]) -> Tuple[DurationInfo, float, float]:
        """提取音符的持续时间信息"""
        try:
            dur_type = note.duration.type
            beats = float(note.quarterLength)
            seconds = beats * 60 / 120  # 假设默认速度为120
            
            return DurationInfo(type_name=dur_type), beats, seconds
        except Exception as e:
            logger.error(f"提取音符持续时间信息出错: {str(e)}")
            raise XMLConverterError(f"提取音符持续时间信息失败: {str(e)}")