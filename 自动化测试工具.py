#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高级多线程下载速度测试工具
功能：可调线程、单/多线程对比、极限并发测试、实时监控
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
from requests.adapters import HTTPAdapter
from urllib3.util.connection import create_connection
import json

class CustomDNSAdapter(HTTPAdapter):
    """自定义DNS适配器，用于重定向域名到指定IP"""
    def __init__(self, hostname, custom_ip, *args, **kwargs):
        self.hostname = hostname
        self.custom_ip = custom_ip
        super().__init__(*args, **kwargs)
    
    def init_poolmanager(self, *args, **kwargs):
        # 创建自定义的连接函数
        def patched_create_connection(address, *args, **kwargs):
            host, port = address
            if host == self.hostname:
                # 将域名重定向到指定IP
                address = (self.custom_ip, port)
            return create_connection(address, *args, **kwargs)
        
        # 猴子补丁替换连接函数
        original_create_connection = socket.create_connection
        socket.create_connection = patched_create_connection
        
        try:
            super().init_poolmanager(*args, **kwargs)
        finally:
            # 恢复原始函数
            socket.create_connection = original_create_connection

class AdvancedDownloadTester:
    def __init__(self, url, custom_ip=None):
        self.url = url
        self.custom_ip = custom_ip
        
        # 解析URL
        self.parsed_url = urlparse(url)
        self.hostname = self.parsed_url.hostname
        self.port = self.parsed_url.port or (443 if self.parsed_url.scheme == 'https' else 80)
        
        # 确定目标IP和模式
        self.target_ip = custom_ip if custom_ip else None
        self.connection_mode = "指定IP" if custom_ip else "DNS解析"
        
        # 测试结果存储
        self.test_results = {}  # 存储不同测试的结果
        
    def get_target_ip(self):
        """获取目标服务器IP地址"""
        print(f"目标服务器: {self.hostname}")
        
        if self.custom_ip:
            print(f"连接模式: 指定IP ({self.custom_ip})")
            self.target_ip = self.custom_ip
        else:
            try:
                resolved_ip = socket.gethostbyname(self.hostname)
                print(f"连接模式: DNS解析 ({resolved_ip})")
                self.target_ip = resolved_ip
            except Exception as e:
                print(f"DNS解析失败: {e}")
                self.target_ip = "未知"
    
    def create_session(self):
        """创建HTTP会话"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # 如果指定了自定义IP，使用自定义DNS适配器
        if self.custom_ip:
            adapter = CustomDNSAdapter(self.hostname, self.custom_ip)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
        
        return session
    
    def measure_latency(self, session):
        """测量到目标服务器的延迟"""
        try:
            start_time = time.time()
            response = session.head(self.url, timeout=5)
            end_time = time.time()
            
            if response.status_code == 200:
                latency = (end_time - start_time) * 1000  # 转换为毫秒
                return latency
        except:
            pass
        return None
    
    def single_test(self, num_threads, test_duration, test_name):
        """执行单次测试"""
        print(f"\n开始测试: {test_name}")
        print(f"线程数: {num_threads}, 时长: {test_duration}秒")
        print("-" * 50)
        
        # 数据存储
        download_speeds = deque()
        latencies = deque()
        total_bytes = 0
        start_time = time.time()
        running = True
        lock = threading.Lock()
        
        # 创建会话
        session = self.create_session()
        
        def download_chunk(thread_id):
            """单个线程的下载函数"""
            nonlocal total_bytes, running
            chunk_size = 8192
            thread_bytes = 0
            
            while running:
                try:
                    response = session.get(self.url, stream=True, timeout=10)
                    
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if not running:
                            break
                        
                        if chunk:
                            chunk_len = len(chunk)
                            thread_bytes += chunk_len
                            
                            with lock:
                                total_bytes += chunk_len
                    
                    response.close()
                    
                except Exception as e:
                    if running:  # 只在测试进行中打印错误
                        print(f"线程 {thread_id} 遇到错误: {e}")
                    time.sleep(1)
        
        def monitor_performance():
            """监控性能指标"""
            nonlocal total_bytes, running
            last_bytes = 0
            last_time = time.time()
            
            while running:
                time.sleep(1)
                
                current_time = time.time()
                current_bytes = total_bytes
                
                time_diff = current_time - last_time
                bytes_diff = current_bytes - last_bytes
                
                if time_diff > 0:
                    speed_bps = bytes_diff / time_diff
                    speed_mbps = speed_bps / (1024 * 1024)
                    
                    timestamp = datetime.now()
                    
                    with lock:
                        download_speeds.append((timestamp, speed_mbps))
                    
                    # 测量延迟
                    latency = self.measure_latency(session)
                    if latency:
                        with lock:
                            latencies.append((timestamp, latency))
                    
                    # 打印实时信息
                    elapsed = current_time - start_time
                    total_mb = current_bytes / (1024 * 1024)
                    avg_speed = total_mb / elapsed if elapsed > 0 else 0
                    
                    print(f"\r时间: {elapsed:6.1f}s | "
                          f"总下载: {total_mb:8.2f} MB | "
                          f"实时速度: {speed_mbps:6.2f} MB/s | "
                          f"平均速度: {avg_speed:6.2f} MB/s | "
                          f"延迟: {latency:6.1f}ms" if latency else "延迟: N/A", end="")
                
                last_bytes = current_bytes
                last_time = current_time
        
        # 启动监控线程
        monitor_thread = threading.Thread(target=monitor_performance)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # 启动下载线程
        download_threads = []
        for i in range(num_threads):
            thread = threading.Thread(target=download_chunk, args=(i,))
            thread.daemon = True
            thread.start()
            download_threads.append(thread)
        
        # 等待测试完成
        time.sleep(test_duration)
        running = False
        
        # 计算最终统计
        total_mb = total_bytes / (1024 * 1024)
        avg_speed = total_mb / test_duration
        
        # 存储测试结果
        self.test_results[test_name] = {
            'threads': num_threads,
            'duration': test_duration,
            'total_mb': total_mb,
            'avg_speed': avg_speed,
            'download_speeds': list(download_speeds),
            'latencies': list(latencies),
            'max_speed': max([speed for _, speed in download_speeds]) if download_speeds else 0,
            'min_speed': min([speed for _, speed in download_speeds]) if download_speeds else 0,
            'avg_latency': sum([lat for _, lat in latencies]) / len(latencies) if latencies else 0
        }
        
        print(f"\n{test_name} 完成!")
        print(f"总下载: {total_mb:.2f} MB, 平均速度: {avg_speed:.2f} MB/s")
        
        session.close()
        return self.test_results[test_name]
    
    def find_max_concurrent_connections(self, max_test_threads=200, step=10, test_duration=10):
        """寻找最大并发连接数"""
        print(f"\n开始极限并发测试...")
        print(f"测试范围: 1 - {max_test_threads} 线程")
        print(f"每次增加: {step} 线程")
        print("=" * 60)
        
        max_connections = 1
        best_speed = 0
        concurrent_results = []
        
        current_threads = 1
        while current_threads <= max_test_threads:
            print(f"\n测试 {current_threads} 线程并发...")
            
            try:
                result = self.single_test(current_threads, test_duration, f"并发测试_{current_threads}线程")
                avg_speed = result['avg_speed']
                
                concurrent_results.append({
                    'threads': current_threads,
                    'speed': avg_speed
                })
                
                print(f"✓ {current_threads} 线程: {avg_speed:.2f} MB/s")
                
                # 如果速度提升，更新最佳配置
                if avg_speed > best_speed:
                    best_speed = avg_speed
                    max_connections = current_threads
                
                # 如果连续几次速度下降明显，可能达到瓶颈
                if len(concurrent_results) >= 3:
                    recent_speeds = [r['speed'] for r in concurrent_results[-3:]]
                    if all(recent_speeds[i] >= recent_speeds[i+1] for i in range(len(recent_speeds)-1)):
                        if recent_speeds[0] - recent_speeds[-1] > best_speed * 0.1:  # 下降超过10%
                            print(f"\n检测到性能下降，建议最大并发: {max_connections} 线程")
                            break
                
            except Exception as e:
                print(f"✗ {current_threads} 线程测试失败: {e}")
                break
            
            current_threads += step
        
        # 生成并发测试图表
        self.create_concurrent_chart(concurrent_results, max_connections)
        
        return max_connections, best_speed
    
    def create_concurrent_chart(self, concurrent_results, optimal_threads):
        """创建并发测试图表"""
        if not concurrent_results:
            return
        
        plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        fig, ax = plt.subplots(1, 1, figsize=(12, 8))
        
        threads = [r['threads'] for r in concurrent_results]
        speeds = [r['speed'] for r in concurrent_results]
        
        # 绘制线图和散点图
        ax.plot(threads, speeds, 'b-o', linewidth=2, markersize=6, alpha=0.8)
        ax.fill_between(threads, speeds, alpha=0.3)
        
        # 标记最佳点
        optimal_speed = max(speeds)
        ax.axvline(x=optimal_threads, color='r', linestyle='--', alpha=0.7, 
                  label=f'最佳并发: {optimal_threads} 线程')
        ax.axhline(y=optimal_speed, color='g', linestyle='--', alpha=0.7,
                  label=f'最高速度: {optimal_speed:.2f} MB/s')
        
        ax.set_title(f'极限并发测试 - {self.hostname} | {self.connection_mode}: {self.target_ip}', 
                    fontsize=14, fontweight='bold')
        ax.set_xlabel('并发线程数', fontsize=12)
        ax.set_ylabel('下载速度 (MB/s)', fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.legend()
        
        # 添加配置信息
        config_text = f'目标: {self.hostname}\n连接: {self.connection_mode}\nIP: {self.target_ip}\n最佳并发: {optimal_threads} 线程'
        ax.text(0.02, 0.98, config_text, transform=ax.transAxes, fontsize=10,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
        
        plt.tight_layout()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"concurrent_test_{self.hostname}_{timestamp}.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"\n并发测试图表已保存: {filename}")
        plt.show()
    
    def create_comparison_chart(self, test_configs):
        """创建对比图表"""
        if not self.test_results:
            return
        
        plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
        
        colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown', 'pink', 'gray']
        
        # 1. 下载速度对比图
        for i, (test_name, result) in enumerate(self.test_results.items()):
            if result['download_speeds']:
                times, speeds = zip(*result['download_speeds'])
                ax1.plot(times, speeds, color=colors[i % len(colors)], 
                        linewidth=1.5, label=f"{test_name} ({result['threads']}线程)", alpha=0.8)
        
        ax1.set_title(f'下载速度对比 - {self.hostname} | {self.connection_mode}: {self.target_ip}', 
                     fontsize=12, fontweight='bold')
        ax1.set_ylabel('下载速度 (MB/s)', fontsize=10)
        ax1.grid(True, alpha=0.3)
        ax1.legend(fontsize=9)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        
        # 2. 延迟对比图
        for i, (test_name, result) in enumerate(self.test_results.items()):
            if result['latencies']:
                times, lats = zip(*result['latencies'])
                ax2.plot(times, lats, color=colors[i % len(colors)], 
                        linewidth=1.5, label=f"{test_name}", alpha=0.8)
        
        ax2.set_title('网络延迟对比', fontsize=12, fontweight='bold')
        ax2.set_ylabel('延迟 (ms)', fontsize=10)
        ax2.grid(True, alpha=0.3)
        ax2.legend(fontsize=9)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
        
        # 3. 平均速度柱状图
        test_names = list(self.test_results.keys())
        avg_speeds = [result['avg_speed'] for result in self.test_results.values()]
        thread_counts = [result['threads'] for result in self.test_results.values()]
        
        bars = ax3.bar(range(len(test_names)), avg_speeds, color=colors[:len(test_names)], alpha=0.7)
        ax3.set_title('平均下载速度对比', fontsize=12, fontweight='bold')
        ax3.set_ylabel('平均速度 (MB/s)', fontsize=10)
        ax3.set_xticks(range(len(test_names)))
        ax3.set_xticklabels([f"{name}\n({threads}线程)" for name, threads in zip(test_names, thread_counts)], 
                           fontsize=9, rotation=45)
        ax3.grid(True, alpha=0.3, axis='y')
        
        # 在柱状图上添加数值
        for bar, speed in zip(bars, avg_speeds):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height + height*0.01,
                    f'{speed:.2f}', ha='center', va='bottom', fontsize=9)
        
        # 4. 统计摘要表格
        ax4.axis('tight')
        ax4.axis('off')
        
        table_data = []
        headers = ['测试名称', '线程数', '时长(s)', '总下载(MB)', '平均速度(MB/s)', '最高速度(MB/s)', '平均延迟(ms)']
        
        for test_name, result in self.test_results.items():
            table_data.append([
                test_name,
                str(result['threads']),
                str(result['duration']),
                f"{result['total_mb']:.2f}",
                f"{result['avg_speed']:.2f}",
                f"{result['max_speed']:.2f}",
                f"{result['avg_latency']:.1f}" if result['avg_latency'] > 0 else "N/A"
            ])
        
        table = ax4.table(cellText=table_data, colLabels=headers, cellLoc='center', loc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        table.scale(1.2, 1.5)
        ax4.set_title('测试结果摘要', fontsize=12, fontweight='bold', pad=20)
        
        # 添加配置信息到图表底部
        config_info = []
        for test_name, result in self.test_results.items():
            config_info.append(f"{test_name}: {result['threads']}线程, {result['duration']}秒")
        
        config_text = f"目标: {self.hostname} | 连接模式: {self.connection_mode} | IP: {self.target_ip}\n"
        config_text += "测试配置: " + " | ".join(config_info)
        
        fig.text(0.5, 0.02, config_text, ha='center', fontsize=10, 
                bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.8))
        
        plt.tight_layout()
        plt.subplots_adjust(bottom=0.1)
        
        # 保存图表
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        mode_suffix = f"custom_{self.target_ip}" if self.custom_ip else "dns"
        filename = f"comparison_test_{self.hostname}_{mode_suffix}_{timestamp}.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"\n对比图表已保存为: {filename}")
        
        plt.show()

def get_user_config():
    """获取用户配置"""
    print("=" * 60)
    print("高级下载速度测试工具")
    print("=" * 60)
    
    # 获取基本配置
    url = input("请输入下载链接: ").strip()
    if not url or not url.startswith(('http://', 'https://')):
        print("错误: 请提供有效的下载链接")
        return None
    
    # 询问是否指定自定义IP
    print("\n连接模式选择:")
    print("1. DNS自动解析 (默认)")
    print("2. 指定自定义IP地址")
    
    ip_choice = input("请选择 (1/2，直接回车选择1): ").strip()
    custom_ip = None
    
    if ip_choice == '2':
        custom_ip = input("请输入目标IP地址: ").strip()
        if not custom_ip:
            custom_ip = None
        else:
            try:
                socket.inet_aton(custom_ip)
            except socket.error:
                print("错误: IP地址格式无效，将使用DNS自动解析")
                custom_ip = None
    
    # 选择测试模式
    print("\n测试模式选择:")
    print("1. 单次测试 (自定义线程数和时间)")
    print("2. 单/多线程对比测试")
    print("3. 极限并发测试")
    print("4. 全套自动化测试")
    
    mode = input("请选择测试模式 (1-4): ").strip()
    
    config = {
        'url': url,
        'custom_ip': custom_ip,
        'mode': mode
    }
    
    if mode == '1':
        # 单次测试配置
        try:
            threads = int(input("请输入线程数 (默认32): ") or "32")
            duration = int(input("请输入测试时长(秒) (默认60): ") or "60")
            config.update({'threads': threads, 'duration': duration})
        except ValueError:
            print("输入错误，使用默认值")
            config.update({'threads': 32, 'duration': 60})
    
    elif mode == '2':
        # 对比测试配置
        print("配置对比测试参数:")
        try:
            duration = int(input("每次测试时长(秒) (默认30): ") or "30")
            config.update({'duration': duration})
        except ValueError:
            config.update({'duration': 30})
    
    elif mode == '3':
        # 极限并发测试配置
        try:
            max_threads = int(input("最大测试线程数 (默认200): ") or "200")
            step = int(input("线程递增步长 (默认10): ") or "10")
            duration = int(input("每次测试时长(秒) (默认10): ") or "10")
            config.update({'max_threads': max_threads, 'step': step, 'duration': duration})
        except ValueError:
            config.update({'max_threads': 200, 'step': 10, 'duration': 10})
    
    elif mode == '4':
        # 全套测试配置
        try:
            duration = int(input("每次测试时长(秒) (默认30): ") or "30")
            config.update({'duration': duration})
        except ValueError:
            config.update({'duration': 30})
    
    else:
        print("无效选择，使用默认单次测试")
        config.update({'mode': '1', 'threads': 32, 'duration': 60})
    
    return config

def main():
    """主函数"""
    config = get_user_config()
    if not config:
        return
    
    # 创建测试器
    tester = AdvancedDownloadTester(config['url'], config['custom_ip'])
    tester.get_target_ip()
    
    try:
        if config['mode'] == '1':
            # 单次测试
            print(f"\n执行单次测试...")
            tester.single_test(config['threads'], config['duration'], f"单次测试_{config['threads']}线程")
            tester.create_comparison_chart([config])
            
        elif config['mode'] == '2':
            # 单/多线程对比测试
            print(f"\n执行单/多线程对比测试...")
            test_configs = [
                (1, "单线程测试"),
                (8, "8线程测试"),
                (16, "16线程测试"),
                (32, "32线程测试"),
                (64, "64线程测试")
            ]
            
            for threads, name in test_configs:
                tester.single_test(threads, config['duration'], name)
            
            tester.create_comparison_chart(test_configs)
            
        elif config['mode'] == '3':
            # 极限并发测试
            max_conn, best_speed = tester.find_max_concurrent_connections(
                config['max_threads'], config['step'], config['duration']
            )
            print(f"\n极限并发测试完成!")
            print(f"推荐最大并发: {max_conn} 线程")
            print(f"最高速度: {best_speed:.2f} MB/s")
            
        elif config['mode'] == '4':
            # 全套自动化测试 (不包含极限并发)
            print(f"\n执行全套自动化测试...")
            
            # 基础性能对比测试
            print("\n执行基础性能对比测试:")
            basic_tests = [
                (1, "单线程基准"),
                (4, "4线程测试"),
                (8, "8线程测试"),
                (16, "16线程测试"),
                (32, "32线程测试"),
                (64, "64线程测试"),
                (128, "128线程测试")
            ]
            
            for threads, name in basic_tests:
                tester.single_test(threads, config['duration'], name)
            
            # 生成完整对比图表
            print("\n生成综合对比报告...")
            tester.create_comparison_chart(basic_tests)
            
            # 输出推荐建议
            best_result = max(tester.test_results.values(), key=lambda x: x['avg_speed'])
            print(f"\n自动化测试完成!")
            print(f"最佳性能配置: {best_result['threads']} 线程")
            print(f"最高平均速度: {best_result['avg_speed']:.2f} MB/s")
            print(f"如需测试极限并发，请选择模式3单独进行")
    
    except KeyboardInterrupt:
        print("\n\n测试被用户中断")
    except Exception as e:
        print(f"\n测试过程中发生错误: {e}")

if __name__ == "__main__":
    main()
