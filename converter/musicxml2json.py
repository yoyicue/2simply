import argparse
import logging
import sys
from src.xml_converter import MusicXMLConverter
from src.debug import ScoreDebugger

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_measure_numbers(arg):
    """将逗号分隔的字符串转换为整数列表"""
    # 处理空值
    if not arg:
        return None
    # 分割字符串并转换为整数
    try:
        # 支持空格或逗号分隔
        numbers = [int(x.strip()) for x in arg.replace(',', ' ').split()]
        return numbers
    except ValueError:
        raise argparse.ArgumentTypeError('小节号必须是整数')

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='将MusicXML文件转换为JSON格式')
    parser.add_argument(
        '--input',
        required=True,
        help='输入的MusicXML文件路径'
    )
    parser.add_argument(
        '--output',
        required=True,
        help='输出的JSON文件路径'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='启用调试模式'
    )
    parser.add_argument(
        '--debug-measures',
        type=parse_measure_numbers,
        help='需要调试的小节号列表 (用逗号或空格分隔)'
    )
    
    return parser.parse_args()

def main():
    """主函数"""
    try:
        # 解析命令行参数
        args = parse_arguments()
        
        # 设置调试器
        debugger = None
        if args.debug or args.debug_measures:
            debugger = ScoreDebugger(measure_numbers=args.debug_measures)
        
        # 创建转换器实例
        converter = MusicXMLConverter(
            xml_path=args.input,
            debugger=debugger
        )
        
        # 直接调用转换器的save_json方法
        converter.save_json(args.output)
        
        logger.info(f"转换完成。输出文件：{args.output}")
        
    except Exception as e:
        logger.error(f"错误：{str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()