# 复现实验协议

## 环境

建议 Python 3.10–3.12。基础流程依赖 NumPy、Pillow、OpenCV 和 plyfile；旧的 per-scene 训练依赖 PyTorch、CUDA 与 gsplat。DGGT 和 Splatt3R 维护独立运行环境，本仓库不合并其 CUDA 扩展。

~~~powershell
python -m pip install -r requirements.txt
git submodule update --init --recursive
~~~

## 数据组织

~~~text
data/raw/                  原始视频、图像或公开数据
data/processed/site/       COLMAP/标准数据适配结果
configs/site.json          米制坐标、已知区域与任务参数
outputs/<scene>/scene.npz  重建场景
~~~

所有路径相对于项目根目录。权重、数据集和输出结果不提交到 Git。

## 计算流程

视频路径为：

视频抽帧 → DGGT/Splatt3R 前馈推理 → scene.npz → 占据风险图 → Hybrid A* → 闭环仿真。

~~~powershell
python -m parking_gs.cli reconstruct-video --video data/raw/site/parking.mp4 --backend dggt --checkpoint D:/weights/model.pth --output outputs/video_site
python -m parking_gs.cli evaluate --scene outputs/video_site/scene.npz
~~~

默认 DGGT 源码为 third_party/dggt；其他 checkout 可通过 repo 参数指定。长视频窗口和尺度对齐见前馈文档。

## 对照实验

旧的 per-scene 3DGS 优化链路可作为重建基线：

~~~powershell
python -m parking_gs.cli train --data data/processed/site --output outputs/site --steps 3000
~~~

规划基线为传统栅格 A*，通过 API 的 planner=astar 选择；默认方法为 Hybrid A*。协方差建图与中心近似的消融由 evaluate --ablation 提供。

## 结果解释

scene.npz 保存激活后的高斯位置、尺度、四元数、颜色、透明度及元数据。泊车状态由闭环仿真的终点误差和碰撞状态定义；其结果不等价于真实车辆性能。

## 复现约束

实验应固定场景划分、车辆参数、地图分辨率、随机种子和规划预算。相邻视频帧存在强相关性，论文实验应按场景或时段划分训练、验证与测试。