# 第三方依赖与许可

## 软件依赖

| 组件 | 用途 | 许可/来源 |
|---|---|---|
| PyTorch | 张量与自动微分 | 上游许可，https://github.com/pytorch/pytorch |
| gsplat 1.5.3 | 可微高斯光栅化 | Apache-2.0，https://github.com/nerfstudio-project/gsplat |
| NumPy、Pillow | 数值计算与图像 | BSD-3-Clause / HPND |
| OpenCV-Python | 视频解码 | Apache-2.0，https://github.com/opencv/opencv-python |
| plyfile | PLY 读取 | MIT，https://github.com/dranjan/plyfile |
| COLMAP | 旧基线的数据预处理 | BSD-3-Clause，https://github.com/colmap/colmap |

## Submodule

| 仓库 | 目录 | 许可 | 作用 |
|---|---|---|---|
| DGGT | third_party/dggt | Apache-2.0 | 视频前馈重建 |
| Splatt3R | third_party/splatt3r | CC BY-NC 4.0 | 图像对前馈重建 |

Submodule 仅固定源码提交；模型权重、数据集和独立环境不在本仓库中。分发或商业使用时必须同时遵守上游许可证与权利声明。

## 方法参考

- Kerbl et al., 3D Gaussian Splatting for Real-Time Radiance Field Rendering.
- Ye et al., gsplat: An Open-Source Library for Gaussian Splatting.
- PythonRobotics Hybrid A* documentation.
- COLMAP model format documentation。

本项目自行实现视频抽帧、场景归一化、风险建图、泊车规划、控制仿真和可视化；不将第三方方法宣称为原创。