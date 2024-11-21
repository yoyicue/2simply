import json
import asyncio
import aiohttp
import typer
from pathlib import Path
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.console import Console
from typing import Dict

app = typer.Typer()
console = Console()

API_KEY = "YOUR_SCRAPERAPI_KEY"
BASE_URL = "http://api.scraperapi.com"
ASSET_BASE_URL = "https://assets.joytunes.com/play_assets"
CONCURRENT_REQUESTS = 10  # 增加到10个并行请求
TIMEOUT = 60  # 保持较长的超时时间
BATCH_SIZE = 10  # 批次大小与并发数保持一致
RETRY_DELAY = 1  # 重试间隔时间（秒）

async def download_file(session: aiohttp.ClientSession, 
                       filename: str, 
                       md5: str, 
                       output_dir: Path,
                       progress: Progress,
                       task_id: int,
                       debug: bool = False,
                       use_proxy: bool = False) -> None:
    """下载单个文件"""
    # 处理文件名和后缀
    file_path = Path(filename)
    base_filename = file_path.stem
    original_suffix = file_path.suffix.lower()  # 转换为小写以便比较
    
    # 构建下载URL
    target_url = f"{ASSET_BASE_URL}/{base_filename}-{md5}{original_suffix}"
    url = f"{BASE_URL}?api_key={API_KEY}&url={target_url}" if use_proxy else target_url
    
    if debug:
        console.print(f"[yellow]Target URL: {target_url}")
        console.print(f"[yellow]Final URL: {url}")
        console.print(f"[yellow]Mode: {'Proxy' if use_proxy else 'Direct'}")
    
    output_path = output_dir / f"{base_filename}-{md5}{original_suffix}"
    
    progress.update(task_id, description=f"[cyan]Downloading: {filename}")
    
    if output_path.exists():
        progress.update(task_id, advance=1)
        console.print(f"[blue]Skipped existing file: {filename}")
        return

    try:
        timeout = aiohttp.ClientTimeout(total=TIMEOUT)
        async with session.get(url, timeout=timeout) as response:
            if response.status == 200:
                # 根据文件类型决定读取模式
                if original_suffix in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.mp3', '.wav']:
                    # 二进制文件
                    content = await response.read()
                    output_path.write_bytes(content)
                else:
                    # 文本文件
                    content = await response.text()
                    output_path.write_text(content)
                    
                progress.update(task_id, advance=1)
                console.print(f"[green]Successfully downloaded ({progress.tasks[0].completed}/{progress.tasks[0].total}): {filename}")
            else:
                console.print(f"[red]Error downloading {filename}: Status {response.status}")
    except asyncio.TimeoutError:
        console.print(f"[yellow]Timeout downloading {filename}")
    except Exception as e:
        console.print(f"[red]Error downloading {filename}: {str(e)}")

async def download_batch(session: aiohttp.ClientSession,
                        batch: list,
                        output_dir: Path,
                        progress: Progress,
                        task_id: int):
    """下载一批文件"""
    tasks = []
    for filename, md5 in batch:
        tasks.append(download_file(session, filename, md5, output_dir, progress, task_id))
    await asyncio.gather(*tasks)

async def download_all(file_map: Dict[str, str], output_dir: Path, debug: bool = False, use_proxy: bool = False):
    """异步下载所有文件"""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 将文件列表分批
    items = list(file_map.items())
    batches = [items[i:i + BATCH_SIZE] for i in range(0, len(items), BATCH_SIZE)]
    
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        refresh_per_second=1
    ) as progress:
        task = progress.add_task(
            description="[cyan]Starting downloads...", 
            total=len(file_map)
        )
        
        # 配置连接池
        conn = aiohttp.TCPConnector(
            limit=CONCURRENT_REQUESTS,
            limit_per_host=CONCURRENT_REQUESTS,
            force_close=True,
            enable_cleanup_closed=True
        )
        
        # 配置客户端会话
        timeout = aiohttp.ClientTimeout(
            total=TIMEOUT,
            connect=TIMEOUT/2,
            sock_read=TIMEOUT/2
        )
        
        async with aiohttp.ClientSession(
            connector=conn, 
            timeout=timeout,
            raise_for_status=True
        ) as session:
            for i, batch in enumerate(batches):
                console.print(f"[yellow]Processing batch {i+1}/{len(batches)}")
                tasks = []
                for filename, md5 in batch:
                    tasks.append(download_file(session, filename, md5, output_dir, progress, task, debug, use_proxy))
                await asyncio.gather(*tasks)
                await asyncio.sleep(RETRY_DELAY)  # 批次间的短暂暂停

@app.command()
def main(
    input_file: Path = typer.Argument(..., help="Input BigFilesMD5s.json file path"),
    output_dir: Path = typer.Argument(..., help="Output directory for downloaded files"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Debug mode: only download first item"),
    use_proxy: bool = typer.Option(False, "--proxy", "-p", help="Use scraperapi proxy instead of direct connection"),
):
    """
    Download music files using scraperapi
    """
    try:
        content = input_file.read_text()
        content = content.strip()
        if ',' in content:
            last_comma_index = content.rstrip('}').rstrip().rstrip(',')
            content = last_comma_index + '}'
            
        file_map = json.loads(content)
        console.print(f"[green]Found {len(file_map)} files to download")
        
        if debug:
            # 在debug模式下只取第一个项目
            first_item = dict(list(file_map.items())[:1])
            file_map = first_item
            console.print("[yellow]Debug mode: Only downloading first item")
            first_key = list(first_item.keys())[0]
            console.print(f"[yellow]Debug info:")
            console.print(f"[yellow]Filename: {first_key}")
            console.print(f"[yellow]MD5: {first_item[first_key]}")
            console.print(f"[yellow]Full URL: {BASE_URL}?api_key={API_KEY}&url={ASSET_BASE_URL}/{first_key}-{first_item[first_key]}.json")
        
    except Exception as e:
        console.print(f"[red]Error reading input file: {str(e)}")
        raise typer.Exit(1)
    
    try:
        asyncio.run(download_all(file_map, output_dir, debug, use_proxy))
        console.print("[green]Download completed!")
    except Exception as e:
        console.print(f"[red]Error during download: {str(e)}")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()