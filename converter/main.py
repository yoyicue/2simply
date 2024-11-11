import json
import sys
import traceback
import argparse
from src.constants import Score
from src.converter import ScoreConverter
from src.debug import ScoreDebugger

def parse_args():
    parser = argparse.ArgumentParser(description='将JSON格式的乐谱转换为MusicXML格式')
    parser.add_argument('--input', required=True, help='输入的JSON文件路径')
    parser.add_argument('--output', required=True, help='输出的MusicXML文件路径')
    parser.add_argument('--debug-measures', help='需要调试的小节号，用逗号分隔')
    return parser.parse_args()

def main():
    args = parse_args()
    
    try:
        # 读取JSON文件
        with open(args.input, 'r') as f:
            json_data = json.load(f)
        
        # 创建Score对象
        score = Score.from_json(json_data)
        
        # 创建调试器（如果指定了debug_measures）
        debugger = None
        if args.debug_measures:
            debug_measures = [int(m) for m in args.debug_measures.split(',')]
            debugger = ScoreDebugger(debug_measures)
        
        # 创建转换器并转换
        converter = ScoreConverter(score, debugger)  # 直接创建实例
        music21_score = converter.convert()
        
        # 保存为MusicXML
        music21_score.write('musicxml', args.output)
        print(f"成功：乐谱已保存至 {args.output}")
        
    except Exception as e:
        print(f"错误：处理过程中发生异常 - {str(e)}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main() 