# 开源依赖、来源与许可证

资料核对日期：2026-09-12。

## 外部实现依赖

- **gsplat 1.5.3**，https://github.com/nerfstudio-project/gsplat ，Apache-2.0。用于训练阶段可微高斯光栅化，非本项目原创。接口按 https://docs.gsplat.studio/versions/1.5.3/apis/rasterization.html 编写。项目只通过 Python 依赖导入，不复制其源代码。上游许可证：https://github.com/nerfstudio-project/gsplat/blob/main/LICENSE 。
- **PyTorch**，https://github.com/pytorch/pytorch ，上游 LICENSE 为准，用于张量和自动微分。
- **NumPy**，https://github.com/numpy/numpy ，BSD-3-Clause。
- **Pillow**，https://github.com/python-pillow/Pillow ，HPND 等上游声明。
- **OpenCV-Python**，https://github.com/opencv/opencv-python ，Apache-2.0 / OpenCV 上游许可，用于本地视频解码与抽帧。
- **plyfile**，https://github.com/dranjan/plyfile ，MIT，用于读取前馈模型输出的 PLY 高斯文件。
- **pytest**，https://github.com/pytest-dev/pytest ，MIT，可选开发测试工具；本项目测试也可用标准库 unittest 执行。
- **COLMAP**，https://github.com/colmap/colmap ，BSD-3-Clause，外部数据预处理工具，未捆绑且未安装。
- **DGGT**，https://github.com/xiaomi-research/dggt ，Apache-2.0，作为外部前馈视频重建后端；仅通过 `scripts/dggt_export_scene.py` 动态导入用户本地 checkout，不复制其代码或权重。
- **Splatt3R**，https://github.com/btsmart/splatt3r ，CC BY-NC 4.0，作为可选图像对前馈后端；本项目不分发其运行时、模型或 checkpoint。商业使用前必须核对上游非商业限制。

分发第三方库二进制/源码时需保留各自完整许可证及适用声明；本文件不是这些许可证的替代文本。当前工程不包含第三方库安装包。

## 算法参考

- Kerbl et al., 3D Gaussian Splatting for Real-Time Radiance Field Rendering，https://repo-sam.inria.fr/fungraph/3d-gaussian-splatting/ 。3DGS 方法的来源，不是本项目提出。
- Ye et al., gsplat: An Open-Source Library for Gaussian Splatting，https://arxiv.org/abs/2409.06765 。
- PythonRobotics Hybrid A* 教学文档，https://atsushisakai.github.io/PythonRobotics/modules/5_path_planning/hybridastar/hybridastar.html 。参考算法类别和工程拆分；本项目规划与控制代码独立编写，不依赖或复制该仓库文件。
- COLMAP 模型格式，https://colmap.github.io/format.html 。用于相机和点云读取。

本项目采用 gsplat 外部渲染后端，并自行实现视频抽帧、前馈输出归一化、泊车建图规划控制和前端。没有克隆修改某一完整泊车仓库，也没有将上游内容改名宣称原创。没有捆绑 Graphdeco 原版 gaussian-splatting 代码，其许可证不应被本项目 MIT 许可证覆盖。

## 数据

KITTI / KITTI-360 使用各自官网规定的数据许可。下载链接和用途见 `docs/02_DATASETS.md`。程序生成的合成场景由本项目代码生成；它不属于 KITTI 数据，也没有真实重建的实测精度。
