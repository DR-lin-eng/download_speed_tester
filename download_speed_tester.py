#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多线程下载速度测试工具
功能：32线程下载，实时监控速度、延迟和IP信息
"""

import threading
import requests
import time
import socket
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from collections import deque
from urllib.parse import urlparse
import sys
import os

class DownloadSpeedTester:
    def __init__(self, url, num_threads=32, test_duration=60, custom_ip=None):
        self.original_url = url
        self.num_threads = num_threads
        self.test_duration = test_duration
        self.custom_ip = custom_ip
        
        # 解析URL并构建实际请求URL
        self.parsed_url = urlparse(url)
        self.hostname = self.parsed_url.hostname
        self.port = self.parsed_url.port or (443 if self.parsed_url.scheme == 'https' else 80)
        
        # 如果指定了自定义IP，替换URL中的hostname
        if custom_ip:
            self.url = url.replace(self.hostname, custom_ip)
            self.target_ip = custom_ip
        else:
            self.url = url
            self.target_ip = None
        
        # 数据存储
        self.download_speeds = deque()  # (timestamp, speed_mbps)
        self.latencies = deque()        # (timestamp, latency_ms)
        self.total_bytes = 0
        self.start_time = None
        
        # 线程控制
        self.running = True
        self.lock = threading.Lock()
        
        # 会话配置
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Host': self.hostname  # 确保Host头部正确
        })
        
    def get_target_ip(self):
        """获取目标服务器IP地址"""
        if self.custom_ip:
            print(f"目标服务器: {self.hostname}")
            print(f"指定IP地址: {self.target_ip} (用户指定)")
        else:
            try:
                self.target_ip = socket.gethostbyname(self.hostname)
                print(f"目标服务器: {self.hostname}")
                print(f"解析IP地址: {self.target_ip} (DNS解析)")
            except Exception as e:
                print(f"DNS解析失败: {e}")
                self.target_ip = "未知"
    
    def measure_latency(self):
        """测量到目标服务器的延迟"""
        try:
            start_time = time.time()
            response = self.session.head(self.url, timeout=5)
            end_time = time.time()
            
            if response.status_code == 200:
                latency = (end_time - start_time) * 1000  # 转换为毫秒
                return latency
        except:
            pass
        return None
    
    def download_chunk(self, thread_id):
        """单个线程的下载函数"""
        chunk_size = 8192
        thread_bytes = 0
        
        while self.running:
            try:
                # 使用流式下载
                response = self.session.get(self.url, stream=True, timeout=10)
                
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if not self.running:
                        break
                    
                    if chunk:
                        chunk_len = len(chunk)
                        thread_bytes += chunk_len
                        
                        with self.lock:
                            self.total_bytes += chunk_len
                
                response.close()
                
            except Exception as e:
                print(f"线程 {thread_id} 遇到错误: {e}")
                time.sleep(1)  # 出错后短暂休息
    
    def monitor_performance(self):
        """监控性能指标"""
        last_bytes = 0
        last_time = time.time()
        
        while self.running:
            time.sleep(1)  # 每秒采样一次
            
            current_time = time.time()
            current_bytes = self.total_bytes
            
            # 计算下载速度
            time_diff = current_time - last_time
            bytes_diff = current_bytes - last_bytes
            
            if time_diff > 0:
                speed_bps = bytes_diff / time_diff
                speed_mbps = speed_bps / (1024 * 1024)  # 转换为 MB/s
                
                timestamp = datetime.now()
                
                with self.lock:
                    self.download_speeds.append((timestamp, speed_mbps))
                    
                # 测量延迟
                latency = self.measure_latency()
                if latency:
                    with self.lock:
                        self.latencies.append((timestamp, latency))
                
                # 打印实时信息
                elapsed = current_time - self.start_time
                total_mb = current_bytes / (1024 * 1024)
                avg_speed = total_mb / elapsed if elapsed > 0 else 0
                
                print(f"\r时间: {elapsed:6.1f}s | "
                      f"总下载: {total_mb:8.2f} MB | "
                      f"实时速度: {speed_mbps:6.2f} MB/s | "
                      f"平均速度: {avg_speed:6.2f} MB/s | "
                      f"延迟: {latency:6.1f}ms" if latency else "延迟: N/A", end="")
            
            last_bytes = current_bytes
            last_time = current_time
    
    def create_charts(self):
        """创建性能图表"""
        plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        
        # 下载速度图表
        if self.download_speeds:
            times, speeds = zip(*self.download_speeds)
            ax1.plot(times, speeds, 'b-', linewidth=1.5, alpha=0.8)
            ax1.fill_between(times, speeds, alpha=0.3)
            title = f'下载速度波动图 - {self.hostname}'
            if self.custom_ip:
                title += f' (IP: {self.custom_ip})'
            ax1.set_title(title, fontsize=14, fontweight='bold')
            ax1.set_ylabel('下载速度 (MB/s)', fontsize=12)
            ax1.grid(True, alpha=0.3)
            ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            ax1.xaxis.set_major_locator(mdates.SecondLocator(interval=10))
            
            # 添加统计信息
            avg_speed = sum(speeds) / len(speeds)
            max_speed = max(speeds)
            min_speed = min(speeds)
            ax1.axhline(y=avg_speed, color='r', linestyle='--', alpha=0.7, label=f'平均: {avg_speed:.2f} MB/s')
            ax1.legend()
            
            # 在图上添加统计文本
            stats_text = f'最大: {max_speed:.2f} MB/s\n最小: {min_speed:.2f} MB/s\n平均: {avg_speed:.2f} MB/s'
            ax1.text(0.02, 0.98, stats_text, transform=ax1.transAxes, fontsize=10,
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        # 延迟图表
        if self.latencies:
            times, lats = zip(*self.latencies)
            ax2.plot(times, lats, 'r-', linewidth=1.5, alpha=0.8)
            ax2.fill_between(times, lats, alpha=0.3, color='red')
            ax2.set_title('网络延迟波动图', fontsize=14, fontweight='bold')
            ax2.set_ylabel('延迟 (ms)', fontsize=12)
            ax2.set_xlabel('时间', fontsize=12)
            ax2.grid(True, alpha=0.3)
            ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            ax2.xaxis.set_major_locator(mdates.SecondLocator(interval=10))
            
            # 添加延迟统计信息
            avg_lat = sum(lats) / len(lats)
            max_lat = max(lats)
            min_lat = min(lats)
            ax2.axhline(y=avg_lat, color='g', linestyle='--', alpha=0.7, label=f'平均: {avg_lat:.1f} ms')
            ax2.legend()
            
            # 在图上添加统计文本
            lat_stats = f'最大: {max_lat:.1f} ms\n最小: {min_lat:.1f} ms\n平均: {avg_lat:.1f} ms'
            ax2.text(0.02, 0.98, lat_stats, transform=ax2.transAxes, fontsize=10,
                    verticalalignment='top', bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.8))
        
        plt.tight_layout()
        
        # 保存图表
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"download_test_{timestamp}.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"\n\n图表已保存为: {filename}")
        
        plt.show()
    
    def run_test(self):
        """运行下载测试"""
        print("=" * 60)
        print("多线程下载速度测试工具")
        print("=" * 60)
        
        # 获取目标IP
        self.get_target_ip()
        
        print(f"原始链接: {self.original_url}")
        if self.custom_ip:
            print(f"实际请求: {self.url}")
        print(f"线程数量: {self.num_threads}")
        print(f"测试时长: {self.test_duration} 秒")
        print("=" * 60)
        
        self.start_time = time.time()
        
        # 启动监控线程
        monitor_thread = threading.Thread(target=self.monitor_performance)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # 启动下载线程
        download_threads = []
        for i in range(self.num_threads):
            thread = threading.Thread(target=self.download_chunk, args=(i,))
            thread.daemon = True
            thread.start()
            download_threads.append(thread)
        
        print("测试进行中...")
        print("实时数据:")
        
        # 等待测试完成
        time.sleep(self.test_duration)
        
        # 停止所有线程
        self.running = False
        
        print("\n\n测试完成！正在生成报告...")
        
        # 最终统计
        total_mb = self.total_bytes / (1024 * 1024)
        avg_speed = total_mb / self.test_duration
        
        print("\n" + "=" * 60)
        print("测试结果汇总")
        print("=" * 60)
        print(f"目标IP地址: {self.target_ip}")
        print(f"测试时长: {self.test_duration} 秒")
        print(f"总下载量: {total_mb:.2f} MB")
        print(f"平均速度: {avg_speed:.2f} MB/s")
        print(f"线程数量: {self.num_threads}")
        
        if self.latencies:
            latency_values = [lat for _, lat in self.latencies]
            avg_latency = sum(latency_values) / len(latency_values)
            min_latency = min(latency_values)
            max_latency = max(latency_values)
            print(f"平均延迟: {avg_latency:.1f} ms")
            print(f"最小延迟: {min_latency:.1f} ms")
            print(f"最大延迟: {max_latency:.1f} ms")
        
        print("=" * 60)
        
        # 生成图表
        self.create_charts()

def main():
    """主函数"""
    print("多线程下载速度测试工具")
    print("请确保已安装必要的库: pip install requests matplotlib")
    print()
    
    # 获取用户输入
    url = input("请输入下载链接: ").strip()
    
    if not url:
        print("错误: 请提供有效的下载链接")
        return
    
    # 验证URL格式
    if not url.startswith(('http://', 'https://')):
        print("错误: URL必须以 http:// 或 https:// 开头")
        return
    
    # 询问是否指定自定义IP
    print("\n是否指定自定义IP地址？")
    print("1. 使用DNS自动解析 (默认)")
    print("2. 指定自定义IP地址")
    
    choice = input("请选择 (1/2，直接回车选择1): ").strip()
    
    custom_ip = None
    if choice == '2':
        custom_ip = input("请输入目标IP地址: ").strip()
        if not custom_ip:
            print("未输入IP地址，将使用DNS自动解析")
            custom_ip = None
        else:
            # 简单验证IP格式
            try:
                socket.inet_aton(custom_ip)
                print(f"将连接到指定IP: {custom_ip}")
            except socket.error:
                print("错误: IP地址格式无效，将使用DNS自动解析")
                custom_ip = None
    
    try:
        # 创建测试实例并运行
        tester = DownloadSpeedTester(url, num_threads=32, test_duration=60, custom_ip=custom_ip)
        tester.run_test()
        
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    except Exception as e:
        print(f"\n测试过程中发生错误: {e}")

if __name__ == "__main__":
    main()
