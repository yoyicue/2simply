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
from typing import List, Tuple, Dict, Any
from tqdm import tqdm
import subprocess
import psutil

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
        self.pass_count = 0
        self.fail_count = 0
        self.error_details: Dict[str, str] = {}
        self.start_time = time.time()
    
    def add_success(self, filename: str):
        self.successful_files += 1
        self.total_files += 1
    
    def add_failure(self, filename: str, error: str):
        self.failed_files += 1
        self.total_files += 1
        self.error_details[filename] = error
    
    def add_comparison_result(self, is_pass: bool):
        if is_pass:
            self.pass_count += 1
        else:
            self.fail_count += 1
    
    def success_rate(self) -> float:
        return (self.successful_files / self.total_files * 100) if self.total_files > 0 else 0
    
    def match_rate(self) -> float:
        total_comparisons = self.pass_count + self.fail_count
        return (self.pass_count / total_comparisons * 100) if total_comparisons > 0 else 0
    
    def get_summary(self) -> str:
        duration = time.time() - self.start_time
        summary = [
            f"\n转换统计报告:",
            f"总处理时间: {duration:.2f} 秒",
            f"总文件数: {self.total_files}",
            f"成功数量: {self.successful_files}",
            f"失败数量: {self.failed_files}",
            f"成功率: {self.success_rate():.1f}%",
            f"\n内容匹配统计:",
            f"PASS数量: {self.pass_count}",
            f"FAIL数量: {self.fail_count}",
            f"匹配率: {self.match_rate():.1f}%"
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

def process_single_file(args: Tuple[Path, Path, Path, bool, Any]) -> Tuple[str, bool, str]:
    input_file, temp_dir, output_base_dir, keep_output, shared_stats = args
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
            error_msg = f"创建输出目录��败 {output_dir} ({str(e)})"
            log_error(input_file, error_msg)
            return str(input_file), False, error_msg
        
        base_name = input_file.name
        if '.ism-' in base_name:
            base_name = base_name.split('.ism-')[0]
        if base_name.endswith('.musicxml'):
            base_name = base_name[:-9]
        
        temp_musicxml = (output_dir if keep_output else temp_dir) / f"{base_name}.musicxml"
        output_json = output_dir / f"{base_name}.musicxml.json"
        
        env = os.environ.copy()
        env['PYTHONWARNINGS'] = 'ignore'
        env['DISABLE_LOGGING'] = '1'
        
        # 合并三个操作到一个进程中
        convert_cmd = (
            f"python converter/json2musicxml.py --input {input_file} --output {temp_musicxml} && "
            f"python converter/musicxml2json.py --input {temp_musicxml} --output {output_json} && "
            f"python converter/score_compare.py --quiet {input_file} {output_json}"
        )
        
        process = subprocess.run(
            convert_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True
        )
        
        is_match = process.returncode == 0
        compare_output = process.stdout + process.stderr
        
        logger = logging.getLogger(__name__)
        logger.info(f"对比结果 - {input_file.name}:")
        logger.info(f"{'匹配' if is_match else '不匹配'}")
        if compare_output.strip():
            logger.info("详细对比信息:")
            logger.info("PASS" if is_match else "FAIL")
        
        # 更新共享统计信息
        if is_match:
            with shared_stats.lock:
                shared_stats.pass_count += 1
        else:
            with shared_stats.lock:
                shared_stats.fail_count += 1
        
        if not is_match:
            error_msg = (
                f"转换结果与原始文件不匹配\n"
                f"转换耗时: {time.time() - start_time:.2f}秒\n"
                f"详细信息: {compare_output if compare_output.strip() else '无'}"
            )
            return str(input_file), True, error_msg
        
        return str(input_file), True, ""
        
    except Exception as e:
        error_msg = f"处理过程中发生错误: {str(e)}"
        log_error(input_file, error_msg)
        return str(input_file), False, error_msg

def get_optimal_process_count():
    """
    获取最优进程数
    在 Apple Silicon 芯片上，考虑性能核心和能效核心的特点
    """
    cpu_count = psutil.cpu_count(logical=False)  # 获取物理CPU核心数
    if cpu_count <= 4:
        return max(1, cpu_count - 1)  # 小核心数机器保留一个核心给系统
    else:
        # Apple Silicon 通常有 4-8 个性能核心
        # 使用 75% 的可用核心���避免系统过载
        return max(1, int(cpu_count * 0.75))

def batch_files(files: List[Path], batch_size: int) -> List[List[Path]]:
    """
    将文件列表分成多个批次
    """
    return [files[i:i + batch_size] for i in range(0, len(files), batch_size)]

def process_batch(args: Tuple[List[Path], Path, Path, bool, Any]) -> List[Tuple[str, bool, str]]:
    """
    批量处理文件以减少进程创建开销
    """
    input_files, temp_dir, output_base_dir, keep_output, stats = args
    results = []
    
    # 预创建所有输出目录
    output_dirs = set()
    for input_file in input_files:
        song_folder = get_song_folder_name(input_file.name)
        output_dir = output_base_dir / song_folder
        output_dirs.add(output_dir)
    
    for output_dir in output_dirs:
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
    
    for input_file in input_files:
        result = process_single_file((input_file, temp_dir, output_base_dir, keep_output, stats))
        results.append(result)
    
    return results

def main():
    parser = argparse.ArgumentParser(description='批量转换并比对文件')
    parser.add_argument('--cache-dir', required=True, help='缓存目录')
    parser.add_argument('--keep-output', action='store_true', help='保留中间文件')
    parser.add_argument('--single-process', action='store_true', help='使用单进程模式')
    parser.add_argument('--batch-size', type=int, default=10, help='每批处理的文件数量')
    args = parser.parse_args()
    
    try:
        # 使用 cache_dir 作为基础目录
        base_path = Path(args.cache_dir)
        temp_dir = base_path / "temp_musicxml"
        output_dir = base_path / "output"
        
        # 设置目录
        temp_dir.mkdir(exist_ok=True)
        output_dir.mkdir(exist_ok=True)
        
        # 查找输入文件
        input_files = find_input_files(args.cache_dir)
        
        if not input_files:
            log_and_print("未找到符合条件的输入文件", "warning")
            return
        
        stats = ConversionStats()
        
        if args.single_process:
            with tqdm(total=len(input_files), desc="处理进度") as pbar:
                for input_file in input_files:
                    if not input_file.exists():
                        log_and_print(f"文件不存在: {input_file}", "error")
                        continue
                    
                    result = process_single_file((input_file, temp_dir, output_dir, args.keep_output, stats))
                    filename, success, error = result
                    
                    if success:
                        stats.add_success(filename)
                    else:
                        stats.add_failure(filename, error)
                        log_and_print(f"处理失败 - {filename}: {error}", "error")
                    
                    pbar.update(1)
        else:
            # 创建进程安全的共享统计对象
            manager = mp.Manager()
            shared_stats = manager.Namespace()
            shared_stats.pass_count = 0
            shared_stats.fail_count = 0
            shared_stats.lock = manager.Lock()  # 添加锁以确保线程安全
            
            # 获取最优进程数
            process_count = get_optimal_process_count()
            log_and_print(f"使用 {process_count} 个进程进行并行处理")
            
            # 将文件分批
            batches = batch_files(input_files, args.batch_size)
            
            def update_stats(batch_results):
                for filename, success, error in batch_results:
                    if success:
                        stats.add_success(filename)
                    else:
                        stats.add_failure(filename, error)
                        log_and_print(f"处理失败 - {filename}: {error}", "error")
                    pbar.update(1)
            
            def error_callback(error):
                log_and_print(f"进程错误: {str(error)}", "error")
            
            with mp.Pool(processes=process_count) as pool:
                with tqdm(total=len(input_files), desc="处理进度") as pbar:
                    process_args = [(batch, temp_dir, output_dir, args.keep_output, shared_stats) for batch in batches]
                    for batch_results in pool.imap_unordered(process_batch, process_args):
                        update_stats(batch_results)
            
            # 更新主进程的统计信息
            stats.pass_count = shared_stats.pass_count
            stats.fail_count = shared_stats.fail_count
        
        # 输出统计信息
        log_and_print(stats.get_summary())
        
        # 清理临时文件
        if not args.keep_output and temp_dir.exists():
            for file in temp_dir.glob("*"):
                try:
                    file.unlink()
                except Exception as e:
                    log_and_print(f"清理临时文件失败 - {file}: {str(e)}", "warning")
            temp_dir.rmdir()
    
    except KeyboardInterrupt:
        log_and_print("\n用户中断处理", "warning")
    except Exception as e:
        log_and_print(f"发生错误: {str(e)}", "error")
        raise

if __name__ == '__main__':
    main() 