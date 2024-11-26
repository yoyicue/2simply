# 2Simply - Simply Piano JSON ⟷ MusicXML Converter

A Python-based tool for bidirectional conversion between Simply Piano's proprietary JSON sheet music format and standard MusicXML format.

## Features

- Convert Simply Piano JSON format to standard MusicXML
- Convert standard MusicXML to Simply Piano JSON format
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

## Tools

The `tools/` directory contains utility scripts for testing and batch processing:

- `batch_convert_compare.py`: A parallel processing tool that performs batch conversion and validation:
  - Converts multiple JSON files to MusicXML and back
  - Automatically compares conversion results
  - Features parallel processing for improved performance
  - Includes progress tracking and detailed logging
  - Optional output file retention for debugging

- `score_compare.py`: A comprehensive music score comparison tool:
  - Performs detailed note-by-note comparison
  - Supports configurable tolerance for floating-point values
  - Can compare specific measures or entire scores
  - Provides rich console output with detailed difference reporting
  - Quiet mode for automated testing

- `dlc_download.py`: Downloads music files with support for batch processing and proxy:
  - Concurrent downloads with configurable batch size
  - Progress tracking with rich console output
  - Optional proxy support through scraperapi
  - Debug mode for testing
  - Handles both binary (images, audio) and text files
  - Supports automatic retries and error handling

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
python json2musicxml.py --input input.json --output output.musicxml
```

Optional arguments:
- `--debug`: Enable debug mode for detailed logging
- `--debug-measures "1,3,5-7"`: Debug specific measures (comma-separated or range)

### Converting MusicXML to Simply Piano JSON

```bash
python musicxml2json.py --input input.musicxml --output output.json
```

Optional arguments:
- `--debug`: Enable debug mode for detailed logging
- `--debug-measures "1,3,5-7"`: Debug specific measures (comma-separated or range)

## Technical Details

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

### Project Structure

- `src/`
  - `converter.py`: Main conversion logic for JSON to MusicXML
  - `xml_converter.py`: Main conversion logic for MusicXML to JSON
  - `constants.py`: Shared constants and data structures
  - `debug.py`: Debugging utilities
  - `duration.py`: Duration handling utilities
- `tools/`
  - `batch_convert_compare.py`: Parallel batch conversion and validation tool
  - `score_compare.py`: Detailed music score comparison utility
  - `dlc_download.py`: Music file downloader with batch and proxy support
- `json2musicxml.py`: CLI tool for JSON to MusicXML conversion
- `musicxml2json.py`: CLI tool for MusicXML to JSON conversion

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

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Simply Piano for inspiring this project
- The MusicXML community for maintaining the open standard
- music21 library for MusicXML parsing capabilities 