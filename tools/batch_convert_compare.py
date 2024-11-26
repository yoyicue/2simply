import argparse
import glob
import json
import logging
import multiprocessing as mp
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict
from tqdm import tqdm
import subprocess

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')


# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('batch_convert.log', encoding='utf-8', mode='w')
    ]
)

def log_error(file: Path, error: str):
    """记录错误信息到日志文件"""
    logger = logging.getLogger(__name__)
    logger.error(f"文件: {file}\n错误: {error}")

def log_and_print(message: str, level: str = "info", print_to_console: bool = True):
    """同时记录到日志文件并打印到控制台"""
    logger = logging.getLogger(__name__)
    if level == "error":
        logger.error(message)
        if print_to_console:
            tqdm.write(f"错误: {message}")
    elif level == "warning":
        logger.warning(message)
        if print_to_console:
            tqdm.write(f"警告: {message}")
    else:
        if print_to_console:
            tqdm.write(message)

class ConversionStats:
    def __init__(self):
        self.total_files = 0
        self.successful_files = 0
        self.failed_files = 0
        self.error_details: Dict[str, str] = {}
        self.start_time = time.time()
    
    def add_success(self, filename: str):
        self.successful_files += 1
        self.total_files += 1
    
    def add_failure(self, filename: str, error: str):
        self.failed_files += 1
        self.total_files += 1
        self.error_details[filename] = error
    
    def success_rate(self) -> float:
        return (self.successful_files / self.total_files * 100) if self.total_files > 0 else 0
    
    def get_summary(self) -> str:
        duration = time.time() - self.start_time
        summary = [
            f"\n转换统计报告:",
            f"总处理时间: {duration:.2f} 秒",
            f"总文件数: {self.total_files}",
            f"成功数量: {self.successful_files}",
            f"失败数量: {self.failed_files}",
            f"成功率: {self.success_rate():.1f}%"
        ]
        return "\n".join(summary)

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
    input_file, temp_dir, output_base_dir, keep_output = args
    start_time = time.time()
    
    try:
        song_folder = get_song_folder_name(input_file.name)
        output_dir = output_base_dir / song_folder
        
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            error_msg = f"无法创建输出目录 {output_dir} (权限被拒绝)"
            log_error(input_file, error_msg)
            return str(input_file), False, error_msg
        except Exception as e:
            error_msg = f"创建输出目录失败 {output_dir} ({str(e)})"
            log_error(input_file, error_msg)
            return str(input_file), False, error_msg
        
        base_name = input_file.name
        if '.ism-' in base_name:
            base_name = base_name.split('.ism-')[0]
        
        temp_musicxml = (output_dir if keep_output else temp_dir) / f"{base_name}.musicxml"
        output_json = output_dir / f"{base_name}.musicxml.json"
        
        env = os.environ.copy()
        env['PYTHONWARNINGS'] = 'ignore'
        env['DISABLE_LOGGING'] = '1'
        
        with open(os.devnull, 'w') as devnull:
            json2musicxml_result = subprocess.run(
                ['python', 'converter/json2musicxml.py', '--input', str(input_file), '--output', str(temp_musicxml)],
                stdout=devnull,
                stderr=devnull,
                env=env
            ).returncode
            
        if json2musicxml_result != 0:
            error_msg = "JSON到MusicXML转换失败"
            log_error(input_file, error_msg)
            return str(input_file), False, error_msg
        
        with open(os.devnull, 'w') as devnull:
            musicxml2json_result = subprocess.run(
                ['python', 'converter/musicxml2json.py', '--input', str(temp_musicxml), '--output', str(output_json)],
                stdout=devnull,
                stderr=devnull,
                env=env
            ).returncode
            
        if musicxml2json_result != 0:
            error_msg = "MusicXML到JSON转换失败"
            log_error(input_file, error_msg)
            return str(input_file), False, error_msg
        
        compare_process = subprocess.run(
            ['python', 'converter/score_compare.py', '--quiet', str(input_file), str(output_json)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True
        )
        
        compare_output = compare_process.stdout + compare_process.stderr
        is_match = compare_process.returncode == 0
        
        logger = logging.getLogger(__name__)
        logger.info(f"对比结果 - {input_file.name}:")
        logger.info(f"{'匹配' if is_match else '不匹配'}")
        if compare_output.strip():
            logger.info("详细对比信息:")
            logger.info(compare_output)
        
        if not is_match:
            error_msg = (
                f"转换结果与原始文件不匹配\n"
                f"转换耗时: {time.time() - start_time:.2f}秒\n"
                f"源文件: {input_file}\n"
                f"目标文件: {output_json}\n"
                f"对比详情:\n{compare_output}"
            )
            log_error(input_file, error_msg)
            return str(input_file), False, "对比结果不匹配"
        
        return str(input_file), True, ""
        
    except FileNotFoundError as e:
        error_msg = f"文件未找到: {str(e)}"
        log_error(input_file, error_msg)
        return str(input_file), False, error_msg
    except PermissionError as e:
        error_msg = f"权限错误: {str(e)}"
        log_error(input_file, error_msg)
        return str(input_file), False, error_msg
    except Exception as e:
        error_msg = f"处理过程中发生错误: {str(e)}"
        log_error(input_file, error_msg)
        return str(input_file), False, error_msg

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
        
        # 初始化统计对象
        stats = ConversionStats()
        
        if args.input_file:
            # 单文件模式
            input_file = Path(args.input_file)
            if not input_file.exists():
                log_and_print(f"输入文件不存在: {input_file}", "error")
                return
            
            result = process_single_file((input_file, temp_dir, output_dir, args.keep_output))
            filename, match, error = result
            
            if match:
                stats.add_success(filename)
            else:
                stats.add_failure(filename, error)
        else:
            # 批处理模式
            input_files = find_input_files(args.cache_dir)
            total_files = len(input_files)
            log_and_print(f"找到 {total_files} 个文件需要处理", print_to_console=True)
            
            if total_files == 0:
                log_and_print("未找到符合条件的文件", "warning", print_to_console=True)
                return
            
            # 准备进程池参数
            process_args = [(f, temp_dir, output_dir, args.keep_output) for f in input_files]
            
            # 使用进程池处理文件
            with mp.Pool(processes=args.processes) as pool:
                results = []
                with tqdm(total=total_files, desc="处理进度", unit="files") as pbar:
                    for result in pool.imap_unordered(process_single_file, process_args):
                        filename, match, error = result
                        if match:
                            stats.add_success(filename)
                        else:
                            stats.add_failure(filename, error)
                        results.append(result)
                        pbar.update()
        
        # 输出统计报告
        summary = stats.get_summary()
        log_and_print(summary, print_to_console=True)
        
    except Exception as e:
        log_and_print(str(e), "error", print_to_console=True)
        sys.exit(1)
    finally:
        # 只有在不保留输出的情况下才清理目录
        if not args.keep_output:
            logger = logging.getLogger(__name__)
            try:
                # 清理临时目录
                if temp_dir.exists():
                    for file in temp_dir.glob("*"):
                        try:
                            file.unlink()
                        except Exception as e:
                            logger.warning(f"清理文件失败 {file}: {str(e)}")
                    temp_dir.rmdir()
                
                # 清理输出目录
                if output_dir.exists():
                    for root, dirs, files in os.walk(output_dir, topdown=False):
                        for name in files:
                            try:
                                (Path(root) / name).unlink()
                            except Exception as e:
                                logger.warning(f"清理文件失败 {name}: {str(e)}")
                        for name in dirs:
                            try:
                                (Path(root) / name).rmdir()
                            except Exception as e:
                                logger.warning(f"清理目录失败 {name}: {str(e)}")
                    output_dir.rmdir()
            except Exception as e:
                logger.warning(f"清理过程中发生错误: {str(e)}")

if __name__ == '__main__':
    main() 