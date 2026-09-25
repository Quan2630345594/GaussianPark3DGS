# Gaussian Park：基于 3D Gaussian Splatting 的泊车研究

## 摘要

本项目研究“视频前馈式三维高斯重建—占据风险建模—Hybrid A* 泊车规划”的闭环。输入为未标定视频，DGGT 预测相机位姿、深度和高斯场；系统将其归一化为统一的米制场景，投影为带未知区域约束的占据风险图，并在车辆自行车模型下搜索前进/倒车轨迹。规划结果通过 Pure Pursuit 闭环仿真评估，并由浏览器进行三维与鸟瞰可视化。

本项目是研究原型，不实现单网络 image-to-control，也不提供实车安全保证。DGGT 与 Splatt3R 源码以 submodule 固定，权重和数据集外置。

## 方法组成

| 层次 | 实现 |
|---|---|
| 重建 | DGGT 视频前馈；Splatt3R 图像对适配；PLY/NPZ 归一化 |
| 表示 | 带旋转协方差的 3D Gaussian scene.npz |
| 建图 | 高度过滤、协方差投影、几何膨胀、known 区域约束 |
| 规划 | Hybrid A*、自行车运动学、前进/倒车与 CSC 连接 |
| 执行 | Pure Pursuit 闭环仿真及碰撞停止 |
| 可视化 | 高斯预览、BEV 风险图、轨迹回放与 JSON 结果 |

## 复现入口

~~~powershell
git clone --recurse-submodules https://github.com/Quan2630345594/GaussianPark3DGS.git
cd GaussianPark3DGS
python -m pip install -r requirements.txt
python -m parking_gs.server
~~~

视频重建需要外部 CUDA 环境和 DGGT checkpoint；源码默认位于 third_party/dggt。

~~~powershell
python -m parking_gs.cli reconstruct-video --video data/raw/site/parking.mp4 --backend dggt --checkpoint D:/weights/model.pth --output outputs/video_site
python -m parking_gs.cli evaluate --scene outputs/video_site/scene.npz
~~~

无真实数据时可用合成场景验证规划与控制：

~~~powershell
python -m parking_gs.cli demo
python -m parking_gs.cli evaluate --scene outputs/demo/scene.npz --ablation
python -m unittest discover -s tests -v
~~~

## 研究边界

当前验证覆盖场景序列化、风险建图、Hybrid A*、控制仿真和 HTTP 接口；尚未验证真实视频的重建精度、跨场景泛化、动态障碍、视觉定位、执行器动力学或实车闭环。合成场景仅用于软件回归。

## 文档

- [复现实验协议](docs/01_QUICKSTART.md)
- [数据与坐标标定](docs/02_DATASETS.md)
- [系统方法](docs/03_ARCHITECTURE.md)
- [创新假设与实验设计](docs/04_INNOVATIONS.md)
- [API 与扩展接口](docs/05_API_AND_DEVELOPMENT.md)
- [验证结果](docs/06_VALIDATION.md)
- [前馈视频重建](docs/07_FEEDFORWARD_VIDEO.md)
- [第三方依赖与许可](THIRD_PARTY_NOTICES.md)

## 许可

本项目代码采用 MIT 许可证。DGGT 采用 Apache-2.0；Splatt3R 采用 CC BY-NC 4.0。第三方源码、权重和数据集须遵循各自许可。