import argparse
import glob
import json
import logging
import multiprocessing as mp
import os
import sys
from pathlib import Path
from typing import List, Tuple
from tqdm import tqdm

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('batch_convert.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def setup_directories(base_dir: str) -> Tuple[Path, Path, Path]:
    """设置必要的目录结构"""
    base_path = Path(base_dir)
    temp_dir = base_path / "temp_musicxml"
    output_dir = base_path / "output"
    
    # 创建临时目录
    temp_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    
    return base_path, temp_dir, output_dir

def find_input_files(cache_dir: str) -> List[Path]:
    """查找所有符合条件的输入文件"""
    pattern = os.path.join(cache_dir, "**", "*.json")
    all_files = glob.glob(pattern, recursive=True)
    
    # 过滤文件
    input_files = [
        Path(f) for f in all_files
        if "musicxml.ism" in f
        and "Compact" not in f
    ]
    
    return input_files

def get_song_folder_name(file_name: str) -> str:
    """从文件名中提取歌曲文件夹名
    例如：从 'AintNoSunshine_BillWithers_PreAdvanced.musicxml.ism-hash.json'
    提取 'AintNoSunshine_BillWithers'
    """
    # 移除.ism-hash.json部分
    if '.ism-' in file_name:
        base_name = file_name.split('.ism-')[0]
    else:
        base_name = file_name
        
    # 移除难度标识（如_PreAdvanced, _Intermediate等）
    parts = base_name.split('_')
    if len(parts) >= 2:  # 至少有歌名和作者
        return '_'.join(parts[:-1])  # 返回除最后一部分以外的所有部分
    return base_name

def process_single_file(args: Tuple[Path, Path, Path, bool]) -> Tuple[str, bool, str]:
    """处理单个文件的转换和比较
    
    Returns:
        Tuple[str, bool, str]: (文件名, 是否匹配, 错误信息)
    """
    input_file, temp_dir, output_base_dir, keep_output = args
    try:
        # 从文件名中提取歌曲文件夹名
        song_folder = get_song_folder_name(input_file.name)
        
        # 构建输出目录（使用歌曲名作为文件夹）
        output_dir = output_base_dir / song_folder
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 从输入文件名中提取基础名称（移除.ism-hash.json部分）
        base_name = input_file.name
        if '.ism-' in base_name:
            base_name = base_name.split('.ism-')[0]
        
        # 构建中间musicxml文件名（如果保留输出，则放在输出目录中）
        if keep_output:
            temp_musicxml = output_dir / f"{base_name}.musicxml"
        else:
            temp_musicxml = temp_dir / f"{base_name}.musicxml"
            
        # 构建输出json文件名（使用歌曲文件夹）
        output_json = output_dir / f"{base_name}.musicxml.json"
        
        # 第一步：JSON到MusicXML的转换
        json2musicxml_result = os.system(f'python converter/json2musicxml.py --input "{input_file}" --output "{temp_musicxml}" > /dev/null 2>&1')
        if json2musicxml_result != 0:
            return str(input_file), False, "JSON到MusicXML转换失败"
        
        # 第二步：MusicXML到JSON的转换
        musicxml2json_result = os.system(f'python converter/musicxml2json.py --input "{temp_musicxml}" --output "{output_json}" > /dev/null 2>&1')
        if musicxml2json_result != 0:
            return str(input_file), False, "MusicXML到JSON转换失败"
        
        # 第三步：比较结果
        # 使用新的score_compare.py路径和quiet模式
        compare_result = os.system(f'python converter/score_compare.py "{input_file}" "{output_json}" --quiet')
        
        # 如果不保留输出且文件在临时目录，则清理临时文件
        if not keep_output and temp_musicxml.parent == temp_dir and temp_musicxml.exists():
            temp_musicxml.unlink()
            
        # 根据compare_result的返回值判断是否匹配（0表示匹配，1表示不匹配）
        return str(input_file), compare_result == 0, ""
        
    except Exception as e:
        return str(input_file), False, str(e)

def main():
    parser = argparse.ArgumentParser(description='批量转换和比较音乐文件')
    parser.add_argument('--cache-dir', help='缓存目录路径')
    parser.add_argument('--input-file', help='单个输入文件路径')
    parser.add_argument('--processes', type=int, default=mp.cpu_count(),
                       help='并行处理的进程数（默认使用所有CPU核心）')
    parser.add_argument('--keep-output', action='store_true',
                       help='保留输出文件（包括JSON和MusicXML文件）')
    args = parser.parse_args()
    
    # 检查参数
    if not args.cache_dir and not args.input_file:
        parser.error("必须指定 --cache-dir 或 --input-file 其中之一")
    if args.cache_dir and args.input_file:
        parser.error("--cache-dir 和 --input-file 不能同时指定")
    
    try:
        # 设置目录
        base_path = Path(args.cache_dir if args.cache_dir else os.path.dirname(args.input_file))
        temp_dir = base_path / "temp_musicxml"
        output_dir = base_path / "output"
        
        # 创建必要的目录
        temp_dir.mkdir(exist_ok=True)
        output_dir.mkdir(exist_ok=True)
        
        if args.input_file:
            # 单文件模式
            input_file = Path(args.input_file)
            if not input_file.exists():
                logger.error(f"输入文件不存在: {input_file}")
                return
            
            logger.info(f"处理单个文件: {input_file}")
            result = process_single_file((input_file, temp_dir, output_dir, args.keep_output))
            filename, match, error = result
            
            if match:
                logger.info(f"文件处理成功: {filename}")
                logger.info("对比结果: 完全匹配")
            else:
                logger.error(f"文件处理失败: {filename}")
                if error:
                    logger.error(f"错误信息: {error}")
                else:
                    logger.error("对比结果: 不匹配")
        else:
            # 批处理模式
            input_files = find_input_files(args.cache_dir)
            total_files = len(input_files)
            logger.info(f"找到 {total_files} 个文件需要处理")
            
            if total_files == 0:
                logger.warning("未找到符合条件的文件")
                return
            
            # 准备进程池参数
            process_args = [(f, temp_dir, output_dir, args.keep_output) for f in input_files]
            
            # 使用进程池处理文件
            with mp.Pool(processes=args.processes) as pool:
                results = []
                with tqdm(total=total_files, desc="处理进度") as pbar:
                    for result in pool.imap_unordered(process_single_file, process_args):
                        results.append(result)
                        pbar.update()
            
            # 统计结果
            success = sum(1 for _, match, _ in results if match)
            failed = total_files - success
            
            # 输出统计信息
            logger.info(f"\n处理完成:")
            logger.info(f"总文件数: {total_files}")
            logger.info(f"成功匹配: {success}")
            logger.info(f"匹配失败: {failed}")
            
            # 如果有失败的情况，输出详细信息到日志
            if failed > 0:
                logger.info("\n失败的文件:")
                for filename, match, error in results:
                    if not match:
                        logger.error(f"{filename}: {error if error else '不匹配'}")
        
    except Exception as e:
        logger.error(f"处理过程中发生错误: {str(e)}")
        sys.exit(1)
    finally:
        # 只有在不保留输出的情况下才清理目录
        if not args.keep_output:
            # 清理临时目录
            if temp_dir.exists():
                for file in temp_dir.glob("*"):
                    file.unlink()
                temp_dir.rmdir()
            
            # 清理输出目录
            if output_dir.exists():
                for root, dirs, files in os.walk(output_dir, topdown=False):
                    for name in files:
                        (Path(root) / name).unlink()
                    for name in dirs:
                        (Path(root) / name).rmdir()
                output_dir.rmdir()

if __name__ == '__main__':
    main() 