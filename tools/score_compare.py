import json
import typer
from rich.console import Console
from rich.table import Table
from typing import List, Optional, Dict, Any
from pathlib import Path

app = typer.Typer()
console = Console()

def load_json_file(file_path: str) -> Dict[str, Any]:
    with open(file_path, 'r') as f:
        return json.load(f)

def compare_notes(note1: Dict[str, Any], note2: Dict[str, Any], tolerance: float = 0.01) -> List[str]:
    differences = []
    
    for attr in ['pitchMidiNote', 'pitchName', 'durationBeats', 'positionBeats']:
        if attr not in note1 or attr not in note2:
            differences.append(f"Missing {attr}")
            continue
            
        if attr in ['durationBeats', 'positionBeats']:
            if abs(note1[attr] - note2[attr]) > tolerance:
                differences.append(f"{attr}: {note1[attr]} vs {note2[attr]}")
        else:
            if note1[attr] != note2[attr]:
                differences.append(f"{attr}: {note1[attr]} vs {note2[attr]}")
    
    return differences

def compare_measure(measure1: Dict[str, Any], measure2: Dict[str, Any], tolerance: float = 0.01) -> Dict[str, Any]:
    results = {
        "note_count_match": len(measure1["notes"]) == len(measure2["notes"]),
        "note_count": (len(measure1["notes"]), len(measure2["notes"])),
        "note_differences": [],
        "measure_differences": []
    }
    
    if abs(measure1["startPositionBeats"] - measure2["startPositionBeats"]) > tolerance:
        results["measure_differences"].append(
            f"startPositionBeats: {measure1['startPositionBeats']:.2f} vs {measure2['startPositionBeats']:.2f}"
        )
    
    # Group notes by position
    notes1_by_pos = {}
    notes2_by_pos = {}
    
    for note in measure1["notes"]:
        pos = round(note["positionBeats"] / tolerance) * tolerance
        if pos not in notes1_by_pos:
            notes1_by_pos[pos] = []
        notes1_by_pos[pos].append(note)
        
    for note in measure2["notes"]:
        pos = round(note["positionBeats"] / tolerance) * tolerance
        if pos not in notes2_by_pos:
            notes2_by_pos[pos] = []
        notes2_by_pos[pos].append(note)
    
    # Compare notes at each position
    all_positions = sorted(set(notes1_by_pos.keys()) | set(notes2_by_pos.keys()))
    
    for pos in all_positions:
        notes1 = notes1_by_pos.get(pos, [])
        notes2 = notes2_by_pos.get(pos, [])
        
        if len(notes1) != len(notes2):
            results["note_differences"].append({
                "note_index": len(results["note_differences"]),
                "differences": [f"Different number of notes at position {pos}: {len(notes1)} vs {len(notes2)}"]
            })
            continue
            
        # Sort notes by pitch to match them up (within each position)
        notes1.sort(key=lambda x: x["pitchMidiNote"])
        notes2.sort(key=lambda x: x["pitchMidiNote"])
        
        for i, (note1, note2) in enumerate(zip(notes1, notes2)):
            differences = compare_notes(note1, note2, tolerance)
            if differences:
                results["note_differences"].append({
                    "note_index": len(results["note_differences"]),
                    "differences": differences
                })
    
    return results

def format_comparison_results(measure_num: int, results: Dict[str, Any]) -> Table:
    table = Table(title=f"Measure {measure_num} Comparison")
    
    table.add_column("Category", style="cyan")
    table.add_column("Details", style="yellow")
    
    note_count1, note_count2 = results["note_count"]
    table.add_row(
        "Note Count",
        f"{'✓' if results['note_count_match'] else '✗'} ({note_count1} vs {note_count2})"
    )
    
    if results["measure_differences"]:
        table.add_row(
            "Measure Differences",
            "\n".join(results["measure_differences"])
        )
    
    for diff in results["note_differences"]:
        table.add_row(
            f"Note {diff['note_index'] + 1}",
            "\n".join(diff["differences"])
        )
    
    return table

@app.command()
def compare(
    file1: str = typer.Argument(..., help="Path to the first JSON file"),
    file2: str = typer.Argument(..., help="Path to the second JSON file"),
    measures: str = typer.Option(
        "all",
        "--measures", "-m",
        help="Optional: Measures to compare (e.g., '1,2,3' or '1-3' or 'all')"
    ),
    tolerance: float = typer.Option(
        0.01,
        "--tolerance", "-t",
        help="Optional: Tolerance for floating point comparisons"
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet", "-q",
        help="Optional: Quiet mode - only show output if there are differences"
    )
):
    try:
        score1 = load_json_file(file1)
        score2 = load_json_file(file2)
        
        if measures.lower() == "all":
            measure_indices = range(len(score1["measures"]))
        else:
            if "-" in measures:
                start, end = map(int, measures.split("-"))
                measure_indices = range(start - 1, end)
            else:
                measure_indices = [int(m) - 1 for m in measures.split(",")]
        
        has_differences = False
        
        for idx in measure_indices:
            if idx >= len(score1["measures"]) or idx >= len(score2["measures"]):
                has_differences = True
                if quiet:
                    console.print(f"Error: Measure count mismatch")
                    return
                console.print(f"[red]Error: Measure {idx + 1} not found in both files[/red]")
                continue
                
            results = compare_measure(
                score1["measures"][idx],
                score2["measures"][idx],
                tolerance
            )
            
            if not results["note_count_match"] or results["measure_differences"] or results["note_differences"]:
                has_differences = True
                if quiet:
                    console.print(f"Error: Differences found in measure {idx + 1}")
                    return
                table = format_comparison_results(idx + 1, results)
                console.print(table)
                console.print()
        
        if not has_differences and quiet:
            console.print("Pass")
            
    except FileNotFoundError as e:
        console.print(f"[red]Error: File not found - {e.filename}[/red]")
    except json.JSONDecodeError:
        console.print("[red]Error: Invalid JSON format in one of the files[/red]")
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")

if __name__ == "__main__":
    app() 