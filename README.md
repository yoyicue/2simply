# 2Simply - Simply Piano JSON ⟷ MusicXML Converter

A Python-based tool for bidirectional conversion between Simply Piano's proprietary JSON sheet music format and standard MusicXML format.

## Features

- Convert Simply Piano JSON format to standard MusicXML
- Convert standard MusicXML to Simply Piano JSON format
- Validate conversion results with detailed comparison
- Preserve musical elements including:
  - Notes and rests
  - Chords
  - Time signatures
  - Key signatures
  - Clefs (Treble and Bass)
  - Tuplets
  - Ties
  - Tempo markings
  - Staff layout and spacing

## Current Limitations

- This codebase was initially generated using Cursor AI, which may affect code quality and reliability
- The JSON to MusicXML conversion currently does not fully implement width constraints from the original JSON format
- Compact layout width calculations are not yet supported
- Some musical notations may not be perfectly preserved during conversion
- Time signatures with X/8 format (e.g., 6/8, 3/8) are not currently supported
- The score comparison tool (`score_compare.py`) only supports comparing Simply Piano JSON files, not MusicXML files

## Tools and Components

### Core Components (`converter/`)
- `json2musicxml.py`: Convert Simply Piano JSON to MusicXML
- `musicxml2json.py`: Convert MusicXML to Simply Piano JSON
- `score_compare.py`: Enhanced JSON score comparison tool with features:
  - Detailed note-level comparison of Simply Piano JSON files
  - Support for both quiet mode (`--quiet`) and verbose mode (`--verbose`)
  - Color-coded output for better readability
  - Exit codes for CI/CD integration (0 for match, 1 for differences)
  - Configurable tolerance for floating-point comparisons
  Note: This tool is specifically designed for comparing Simply Piano JSON files and cannot be used for MusicXML comparisons.

### Utility Tools (`tools/`)
- `batch_convert_compare.py`: Parallel batch conversion and validation tool
- `dlc_download.py`: Concurrent downloader for music files

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/2simply.git
cd 2simply
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Converting Simply Piano JSON to MusicXML

```bash
python converter/json2musicxml.py --input input.json --output output.musicxml
```

Optional arguments:
- `--debug`: Enable debug mode for detailed logging
- `--debug-measures "1,3,5-7"`: Debug specific measures (comma-separated or range)

### Converting MusicXML to Simply Piano JSON

```bash
python converter/musicxml2json.py --input input.musicxml --output output.json
```

Optional arguments:
- `--debug`: Enable debug mode for detailed logging
- `--debug-measures "1,3,5-7"`: Debug specific measures (comma-separated or range)

### Comparing Score Files

The score comparison tool is specifically designed for comparing Simply Piano JSON files. It cannot be used for comparing MusicXML files or other formats.

```bash
# Basic comparison of two Simply Piano JSON files
python converter/score_compare.py file1.json file2.json

# Quiet mode (only outputs PASS/FAIL)
python converter/score_compare.py file1.json file2.json --quiet

# Verbose mode (detailed comparison)
python converter/score_compare.py file1.json file2.json --verbose

# Custom tolerance for floating-point comparisons
python converter/score_compare.py file1.json file2.json --tolerance 0.001
```

Note: Both input files must be in Simply Piano JSON format. For comparing conversion results, use the original JSON file and the converted-back JSON file (after MusicXML conversion).

### Batch Processing

```bash
python tools/batch_convert_compare.py --cache-dir /path/to/cache --keep-output
```

Optional arguments:
- `--processes N`: Number of parallel processes (default: CPU count)
- `--keep-output`: Keep intermediate files
- `--input-file`: Process single file instead of directory

## Technical Details

### Project Structure

- `converter/`
  - `src/`
    - `converter.py`: Core conversion logic for JSON to MusicXML
    - `xml_converter.py`: Core conversion logic for MusicXML to JSON
    - `constants.py`: Shared constants and data structures
    - `debug.py`: Debugging utilities
    - `duration.py`: Duration handling utilities
  - `json2musicxml.py`: CLI tool for JSON to MusicXML conversion
  - `musicxml2json.py`: CLI tool for MusicXML to JSON conversion
  - `score_compare.py`: Enhanced music score comparison tool
- `tools/`
  - `batch_convert_compare.py`: Parallel batch processing utility
  - `dlc_download.py`: Music file downloader

### Simply Piano JSON Format

The Simply Piano JSON format represents sheet music with the following structure:

```json
{
  "measures": [
    {
      "number": 1,
      "height": 200.0,
      "notes": [
        {
          "durationBeats": 1.0,
          "durationSeconds": 0.5,
          "durationType": "quarter",
          "height": 10.0,
          "pitchMidiNote": 60,
          "pitchName": "C4",
          "positionBeats": 0.0,
          "positionSeconds": 0.0,
          "tieType": null,
          "width": 10.0,
          "x": 71.6765,
          "y": -40.0,
          "staff": "treble"
        }
      ],
      "staffDistance": 85.0,
      "startPositionBeats": 0.0,
      "startPositionSeconds": 0.0,
      "width": 150.0,
      "x": 71.6765,
      "y": -150.0
    }
  ],
  "pageWidth": 1069.55
}
```

### MusicXML Format

The converter supports standard MusicXML format (version 3.1 and 4.0), which is widely used for sheet music exchange between different music notation software.

## Development

### Adding New Features

1. Implement new musical element handling in both `converter.py` and `xml_converter.py`
2. Add corresponding constants in `constants.py`
3. Update tests to cover new functionality
4. Update documentation

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Acknowledgments

- Simply Piano for inspiring this project
- The MusicXML community for maintaining the open standard
- music21 library for MusicXML parsing capabilities