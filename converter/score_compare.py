import json
import typer
from rich.console import Console
from rich.table import Table
from typing import List, Optional, Dict, Any, Union, Set
from pathlib import Path
import music21

from src.constants import Score, Note, Measure, ClefType
from src.converter import ScoreConverter
from src.duration import DurationManager, DurationInfo

app = typer.Typer()
console = Console()

class EnhancedScoreComparator:
    """增强的乐谱比较器，集成了DurationManager的时序管理和music21的比较功能"""
    
    def __init__(self, tolerance: float = 0.01):
        self.tolerance = tolerance
        self.duration_manager = DurationManager()
    
    def compare_scores(self, file1: str, file2: str) -> Dict[str, Any]:
        """比较两个乐谱文件"""
        try:
            # 加载Score对象
            score1_data = Score.from_json(file1)
            score2_data = Score.from_json(file2)
            
            # 转换为music21对象
            converter1 = ScoreConverter(score1_data)
            converter2 = ScoreConverter(score2_data)
            
            score1_m21 = converter1.convert()
            score2_m21 = converter2.convert()
            
            return self._compare_music21_scores(score1_m21, score2_m21)
            
        except FileNotFoundError as e:
            console.print(f"[red]Error: File not found - {e.filename}[/red]")
            return {"error": f"File not found - {e.filename}"}
        except json.JSONDecodeError:
            console.print("[red]Error: Invalid JSON format in one of the files[/red]")
            return {"error": "Invalid JSON format"}
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
            return {"error": str(e)}
    
    def _compare_music21_scores(self, score1: music21.stream.Score, 
                              score2: music21.stream.Score) -> Dict[str, Any]:
        """比较两个music21 Score对象"""
        results = {
            "metadata_differences": self._compare_metadata(score1, score2),
            "measure_differences": [],
            "total_measures": (len(score1.parts[0].measures(1, None)), len(score2.parts[0].measures(1, None)))
        }
        
        # 比较每个声部
        for part_index, (part1, part2) in enumerate(zip(score1.parts, score2.parts)):
            part_results = self._compare_parts(part1, part2)
            if part_results:
                results["measure_differences"].extend(
                    [{"part": part_index, **diff} for diff in part_results]
                )
        
        return results
    
    def _compare_metadata(self, score1: music21.stream.Score, 
                         score2: music21.stream.Score) -> List[str]:
        """比较乐谱元数据"""
        differences = []
        
        # 比较拍号
        ts1 = score1.getTimeSignatures()[0] if score1.getTimeSignatures() else None
        ts2 = score2.getTimeSignatures()[0] if score2.getTimeSignatures() else None
        if str(ts1) != str(ts2):
            differences.append(f"Time signature: {ts1} vs {ts2}")
        
        # 比较速度标记
        tempo1 = score1.metronomeMarkBoundaries()[0][2] if score1.metronomeMarkBoundaries() else None
        tempo2 = score2.metronomeMarkBoundaries()[0][2] if score2.metronomeMarkBoundaries() else None
        if tempo1 and tempo2 and abs(tempo1.number - tempo2.number) > self.tolerance:
            differences.append(f"Tempo: {tempo1.number} vs {tempo2.number}")
        
        return differences
    
    def _compare_parts(self, part1: music21.stream.Part, 
                      part2: music21.stream.Part) -> List[Dict[str, Any]]:
        """比较两个声部"""
        differences = []
        
        # 获取所有小节
        measures1 = list(part1.measures(1, None))
        measures2 = list(part2.measures(1, None))
        
        # 比较每个小节
        for i in range(min(len(measures1), len(measures2))):
            measure1 = measures1[i]
            measure2 = measures2[i]
            
            measure_diff = self._compare_measures(measure1, measure2)
            if measure_diff:
                differences.append({
                    "measure": i + 1,  # 小节号从1开始
                    **measure_diff
                })
        
        return differences
    
    def _compare_measures(self, measure1: music21.stream.Measure, 
                         measure2: music21.stream.Measure) -> Optional[Dict[str, Any]]:
        """比较两个小节"""
        differences = {
            "note_differences": [],
            "chord_differences": [],
            "rhythm_differences": []
        }
        
        # 获取所有音符和和弦
        notes1 = measure1.notes.stream()
        notes2 = measure2.notes.stream()
        
        # 比较音符数量
        if len(notes1) != len(notes2):
            differences["note_count"] = (len(notes1), len(notes2))
        
        # 按位置组织音符
        notes_by_offset1 = self._group_notes_by_offset(notes1)
        notes_by_offset2 = self._group_notes_by_offset(notes2)
        
        # 比较每个位置的音符
        all_offsets = sorted(set(notes_by_offset1.keys()) | set(notes_by_offset2.keys()))
        for offset in all_offsets:
            elements1 = notes_by_offset1.get(offset, [])
            elements2 = notes_by_offset2.get(offset, [])
            
            diff = self._compare_elements_at_offset(elements1, elements2)
            if diff:
                differences["note_differences"].append({
                    "offset": offset,
                    **diff
                })
        
        return differences if any(differences.values()) else None
    
    def _group_notes_by_offset(self, notes: music21.stream.Stream) -> Dict[float, List]:
        """按位置组织音符"""
        grouped = {}
        for note in notes:
            offset = round(note.offset / self.tolerance) * self.tolerance
            if offset not in grouped:
                grouped[offset] = []
            grouped[offset].append(note)
        return grouped
    
    def _compare_elements_at_offset(self, elements1: List, 
                                  elements2: List) -> Optional[Dict[str, Any]]:
        """比较同一位置的音符元素"""
        if not elements1 and not elements2:
            return None
            
        differences = {}
        
        # 比较音符/和弦数量
        if len(elements1) != len(elements2):
            differences["element_count"] = (len(elements1), len(elements2))
            return differences
        
        # 对音符进行排序（按音高）
        elements1 = sorted(elements1, key=lambda n: n.pitch.midi if hasattr(n, 'pitch') else -1)
        elements2 = sorted(elements2, key=lambda n: n.pitch.midi if hasattr(n, 'pitch') else -1)
        
        # 比较每个元素
        for e1, e2 in zip(elements1, elements2):
            if type(e1) != type(e2):
                differences["type_mismatch"] = (type(e1).__name__, type(e2).__name__)
                continue
                
            if isinstance(e1, music21.chord.Chord):
                chord_diff = self._compare_chords_enhanced(e1, e2)
                if chord_diff:
                    differences["chord"] = chord_diff
            else:
                note_diff = self._compare_notes_enhanced(e1, e2)
                if note_diff:
                    differences["note"] = note_diff
        
        return differences if differences else None
    
    def compare_duration_components(
        self,
        element1: Union[music21.note.Note, music21.note.Rest, music21.chord.Chord],
        element2: Union[music21.note.Note, music21.note.Rest, music21.chord.Chord]
    ) -> Optional[Dict[str, Any]]:
        """比较两个音乐元素的时值组件"""
        # 使用DurationManager提取完整的时值信息
        dur_info1, beats1, seconds1 = self.duration_manager.extract_duration_info(element1)
        dur_info2, beats2, seconds2 = self.duration_manager.extract_duration_info(element2)
        
        differences = {}
        
        # 比较基本时值类型
        if dur_info1.type_name != dur_info2.type_name:
            differences["duration_type"] = (dur_info1.type_name, dur_info2.type_name)
        
        # 比较附点数
        if dur_info1.dots != dur_info2.dots:
            differences["dots"] = (dur_info1.dots, dur_info2.dots)
        
        # 比较实际拍数（考虑连音）
        if abs(beats1 - beats2) > self.tolerance:
            differences["beats"] = (beats1, beats2)
        
        # 比较实际秒数（考虑速度）
        if abs(seconds1 - seconds2) > self.tolerance:
            differences["seconds"] = (seconds1, seconds2)
        
        return differences if differences else None
    
    def _compare_notes_enhanced(
        self,
        note1: music21.note.Note,
        note2: music21.note.Note
    ) -> Optional[Dict[str, Any]]:
        """增强的音符比较，包含详细的时值比较"""
        differences = {}
        
        # 比较音高（考虑等音）
        if not note1.pitch.isEnharmonic(note2.pitch):
            differences["pitch"] = {
                "note1": note1.nameWithOctave,
                "note2": note2.nameWithOctave,
                "midi1": note1.pitch.midi,
                "midi2": note2.pitch.midi
            }
        
        # 使用增强的时值比较
        duration_diff = self.compare_duration_components(note1, note2)
        if duration_diff:
            differences["duration"] = duration_diff
        
        # 比较连音线
        if bool(note1.tie) != bool(note2.tie):
            differences["tie"] = {
                "note1": str(note1.tie.type if note1.tie else None),
                "note2": str(note2.tie.type if note2.tie else None)
            }
        
        # 比较连音符组
        tuplet1 = note1.duration.tuplets[0] if note1.duration.tuplets else None
        tuplet2 = note2.duration.tuplets[0] if note2.duration.tuplets else None
        
        if bool(tuplet1) != bool(tuplet2):
            differences["tuplet"] = {
                "note1": f"{tuplet1.numberNotesActual}/{tuplet1.numberNotesNormal}" if tuplet1 else None,
                "note2": f"{tuplet2.numberNotesActual}/{tuplet2.numberNotesNormal}" if tuplet2 else None
            }
        
        return differences if differences else None
    
    def _compare_chords_enhanced(
        self,
        chord1: music21.chord.Chord,
        chord2: music21.chord.Chord
    ) -> Optional[Dict[str, Any]]:
        """增强的和弦比较，包含详细的时值比较"""
        differences = {}
        
        # 比较和弦音符数量
        if len(chord1.pitches) != len(chord2.pitches):
            differences["pitch_count"] = (len(chord1.pitches), len(chord2.pitches))
            return differences
        
        # 比较每个音高（考虑等音）
        pitches1 = sorted(chord1.pitches, key=lambda p: p.midi)
        pitches2 = sorted(chord2.pitches, key=lambda p: p.midi)
        
        pitch_differences = []
        for i, (p1, p2) in enumerate(zip(pitches1, pitches2)):
            if not p1.isEnharmonic(p2):
                pitch_differences.append({
                    "index": i,
                    "pitch1": p1.nameWithOctave,
                    "pitch2": p2.nameWithOctave,
                    "midi1": p1.midi,
                    "midi2": p2.midi
                })
        
        if pitch_differences:
            differences["pitches"] = pitch_differences
        
        # 使用增强的时值比较
        duration_diff = self.compare_duration_components(chord1, chord2)
        if duration_diff:
            differences["duration"] = duration_diff
        
        return differences if differences else None
    
    def format_comparison_results(self, results: Dict[str, Any]) -> str:
        """格式化比较结果为��读的文本"""
        output = []
        
        if "error" in results:
            return f"Error: {results['error']}"
        
        if "metadata_differences" in results:
            output.append("元数据差异:")
            for diff in results["metadata_differences"]:
                output.append(f"  - {diff}")
        
        if "measure_differences" in results:
            for measure_diff in results["measure_differences"]:
                measure_num = measure_diff["measure"]
                part_num = measure_diff["part"]
                output.append(f"\n小节 {measure_num}, 声部 {part_num}:")
                
                if "note_differences" in measure_diff:
                    for note_diff in measure_diff["note_differences"]:
                        offset = note_diff["offset"]
                        output.append(f"  位置 {offset}:")
                        
                        if "duration" in note_diff:
                            dur_diff = note_diff["duration"]
                            output.append("    时值差异:")
                            if "duration_type" in dur_diff:
                                output.append(f"      - 类型: {dur_diff['duration_type'][0]} vs {dur_diff['duration_type'][1]}")
                            if "dots" in dur_diff:
                                output.append(f"      - 附点: {dur_diff['dots'][0]} vs {dur_diff['dots'][1]}")
                            if "beats" in dur_diff:
                                output.append(f"      - 拍数: {dur_diff['beats'][0]:.3f} vs {dur_diff['beats'][1]:.3f}")
                            if "seconds" in dur_diff:
                                output.append(f"      - 秒数: {dur_diff['seconds'][0]:.3f} vs {dur_diff['seconds'][1]:.3f}")
                        
                        if "pitch" in note_diff:
                            output.append(f"    音高差异: {note_diff['pitch']['note1']} vs {note_diff['pitch']['note2']}")
                        
                        if "tuplet" in note_diff:
                            output.append(f"    连音符差异: {note_diff['tuplet']['note1']} vs {note_diff['tuplet']['note2']}")
        
        return "\n".join(output)

@app.command()
def compare(
    file1: str = typer.Argument(..., help="第一个JSON文件的路径"),
    file2: str = typer.Argument(..., help="第二个JSON文件的路径"),
    tolerance: float = typer.Option(
        0.01,
        "--tolerance", "-t",
        help="浮点数比较的容差值"
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet", "-q",
        help="安静模式 - 只在有差异时显示输出，相同时输出'PASS'，有差异时输出'FAIL'"
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="详细模式 - 显示更多比较信息"
    )
):
    """比较两个乐谱JSON文件的差异"""
    try:
        comparator = EnhancedScoreComparator(tolerance=tolerance)
        results = comparator.compare_scores(file1, file2)
        
        if "error" in results:
            if quiet:
                console.print("[red]FAIL[/red]")
                return 1
            console.print(f"[red]Error: {results['error']}[/red]")
            return 1
        
        has_differences = (
            results.get("metadata_differences") or 
            results.get("measure_differences")
        )
        
        if verbose:
            # 显示基本信息
            console.print("\n[cyan]基本信息:[/cyan]")
            console.print(f"文件1: {file1}")
            console.print(f"文件2: {file2}")
            console.print(f"容差值: {tolerance}")
            
            # 显示总体统计
            total_measures1, total_measures2 = results["total_measures"]
            console.print(f"\n[cyan]总体统计:[/cyan]")
            console.print(f"小节数: {total_measures1} vs {total_measures2}")
            
            # 显示元数据差异
            console.print("\n[cyan]元数据比较:[/cyan]")
            if results.get("metadata_differences"):
                for diff in results["metadata_differences"]:
                    console.print(f"  - {diff}")
            else:
                console.print("  [green]无差异[/green]")
            
            # 显示小节差异
            console.print("\n[cyan]小节比较:[/cyan]")
            if results.get("measure_differences"):
                for measure_diff in results["measure_differences"]:
                    measure_num = measure_diff["measure"]
                    part_num = measure_diff["part"]
                    console.print(f"\n[yellow]小节 {measure_num}, 声部 {part_num}:[/yellow]")
                    
                    if "note_count" in measure_diff:
                        count1, count2 = measure_diff["note_count"]
                        console.print(f"  音符数量: {count1} vs {count2}")
                    
                    if "note_differences" in measure_diff:
                        for note_diff in measure_diff["note_differences"]:
                            offset = note_diff["offset"]
                            console.print(f"\n  [magenta]位置 {offset:.2f}:[/magenta]")
                            
                            if "duration" in note_diff:
                                dur_diff = note_diff["duration"]
                                console.print("    时值差异:")
                                if "duration_type" in dur_diff:
                                    console.print(f"      类型: {dur_diff['duration_type'][0]} vs {dur_diff['duration_type'][1]}")
                                if "dots" in dur_diff:
                                    console.print(f"      附点: {dur_diff['dots'][0]} vs {dur_diff['dots'][1]}")
                                if "beats" in dur_diff:
                                    console.print(f"      拍数: {dur_diff['beats'][0]:.3f} vs {dur_diff['beats'][1]:.3f}")
                                if "seconds" in dur_diff:
                                    console.print(f"      秒数: {dur_diff['seconds'][0]:.3f} vs {dur_diff['seconds'][1]:.3f}")
                            
                            if "pitch" in note_diff:
                                pitch_info = note_diff["pitch"]
                                console.print(f"    音高差异: {pitch_info['note1']} ({pitch_info['midi1']}) vs {pitch_info['note2']} ({pitch_info['midi2']})")
                            
                            if "tuplet" in note_diff:
                                tuplet_info = note_diff["tuplet"]
                                console.print(f"    连音符差异: {tuplet_info['note1']} vs {tuplet_info['note2']}")
            else:
                console.print("  [green]无差异[/green]")
            
            # 显示总结
            console.print("\n[cyan]比较结果总结:[/cyan]")
            if has_differences:
                console.print("[red]发现差异[/red]")
            else:
                console.print("[green]两个文件完全相同[/green]")
        
        elif quiet:
            if has_differences:
                console.print("[red]FAIL[/red]")
                return 1
            else:
                console.print("[green]PASS[/green]")
                return 0
        elif has_differences:
            formatted_results = comparator.format_comparison_results(results)
            console.print(formatted_results)
            return 1
        else:
            console.print("[green]文件完全相同[/green]")
            return 0
            
    except Exception as e:
        if quiet:
            console.print("[red]FAIL[/red]")
        else:
            console.print(f"[red]Error: {str(e)}[/red]")
        return 1

if __name__ == "__main__":
    app() 