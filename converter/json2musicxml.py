import logging
import argparse
import sys
from pathlib import Path
from src.converter import ScoreConverter
from src.debug import ScoreDebugger
from src.constants import Score
from typing import List

# 创建logger
logger = logging.getLogger(__name__)

def setup_logging(debug: bool = False):
    """配置日志系统"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def parse_debug_measures(measure_str: str) -> List[int]:
    """解析调试小节参数
    
    支持的格式:
    - 单个小节: "1"
    - 多个小节: "1,3,5"
    - 小节范围: "1-3"
    - 组合格式: "1,3-5,7,9-11"
    """
    measures = set()
    
    # 分割逗号分隔的部分
    for part in measure_str.split(','):
        part = part.strip()
        try:
            if '-' in part:
                # 处理范围表示法 (例如: "1-3")
                start, end = map(int, part.split('-'))
                if start <= 0 or end <= 0:
                    raise ValueError("小节号必须是正整数")
                if start > end:
                    raise ValueError(f"范围起始值 {start} 大于结束值 {end}")
                measures.update(range(start, end + 1))
            else:
                # 处理单个小节号
                measure = int(part)
                if measure <= 0:
                    raise ValueError("小节号必须是正整数")
                measures.add(measure)
        except ValueError as e:
            logger.error(f"无效的小节号格式 '{part}': {str(e)}")
            sys.exit(1)
    
    # 转换为排序列表
    result = sorted(measures)
    
    # 输出解析结果以便调试
    if result:
        logger.debug(f"将调试以下小节: {result}")
    else:
        logger.warning("未指定任何要调试的小节")
    
    return result

def main():
    parser = argparse.ArgumentParser(description='将JSON格式的乐谱转换为MusicXML格式')
    parser.add_argument('--input', required=True, help='输入的JSON文件路径')
    parser.add_argument('--output', required=True, help='输出的MusicXML文件路径')
    parser.add_argument('--debug-measures', help='需要调试的小节号，用逗号或短横线分隔（例如：1,3,5-7）')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    
    args = parser.parse_args()
    setup_logging(args.debug)
    
    try:
        # 创建调试器（如果指定了debug_measures）
        debugger = None
        if args.debug_measures:
            debug_measures = parse_debug_measures(args.debug_measures)
            if debug_measures:  # 只有在成功解析到小节号时才创建调试器
                debugger = ScoreDebugger(debug_measures)
                logger.info(f"调试模式已启用，将调试以下小节：{debug_measures}")
        
        # 读取JSON文件
        score = Score.from_json(args.input)
        
        # 创建转换器并转换
        converter = ScoreConverter(score, debugger)
        music21_score = converter.convert()
        
        # 保存为MusicXML
        music21_score.write('musicxml', args.output)
        logger.info(f"成功：乐谱已保存至 {args.output}")
        
    except Exception as e:
        logger.error(f"错误：{str(e)}")
        if args.debug:
            logger.exception("详细错误信息：")
        sys.exit(1)

if __name__ == '__main__':
    main() 