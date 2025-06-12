# download_speed_tester
可以针对任意下载链接通过32线程的下载方式来测试下载链接的下载速度与稳定性。并且使用图表输出。

## 输出图表示例
![download_test_bettergi linzefeng top_dns_20250612_185736](https://github.com/user-attachments/assets/7dd56073-40ae-4c4a-ae0d-d76ad36d16d4)
![download_test_bettergi linzefeng top_custom_172 67 138 170_20250612_185612](https://github.com/user-attachments/assets/cc110faf-0d9f-43d8-80c2-4a05c422af62)


## 依赖安装
pip install requests matplotlib

## 如何运行

py download_speed_tester.py

## 功能

1.默认dns解析下载
2.可以指定解析ip下载。

开发日志（留个记忆）：
1.可调线程
2.单线程
3.自动化流程（单/多线程测试后输出图标）
4.可调时间
5.极限单ip并发测试（测试最多少并发）
