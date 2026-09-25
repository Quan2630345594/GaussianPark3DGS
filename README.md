# Gaussian Park：基于 3D Gaussian Splatting 的泊车研究项目

当前主流程是：**视频 → 前馈式 3DGS（DGGT，可选 Splatt3R 适配）→ 高斯占据地图 → Hybrid A* → 闭环车辆仿真 → Web 可视化**。栅格 A* 保留为可选对照，原来的 per-scene 3DGS 优化训练链路也保留为研究对照。

这是可修改、可复现实验的研究原型。它不是单网络联合训练的 image-to-control 策略，也不是可直接接入实车的自动泊车产品。前馈模型代码和权重由你按文档自行放置；项目不会静默下载它们。程序生成场景只用于离线回归测试，前端会明确标记。

## 交付内容

| 模块 | 已实现内容 | 入口 |
|---|---|---|
| 视频与重建 | 视频抽帧、DGGT bridge、Splatt3R/外部命令适配、PLY/NPZ 场景归一化 | `parking_gs/feedforward.py`, `scripts/dggt_export_scene.py` |
| 研究对照 | COLMAP 文本读取、可选 per-scene 3DGS 优化训练 | `parking_gs/dataset.py`, `parking_gs/training.py` |
| 场景存储 | 无 pickle 的 NPZ 格式，完整协方差与场景元信息 | `parking_gs/scene.py` |
| 建图 | 高斯高度过滤、旋转协方差投影、几何膨胀、未知区域不可通行 | `parking_gs/mapping.py` |
| 规划 | Hybrid A*、自行车运动学、正反向 CSC 曲线连接、车辆轮廓验证 | `parking_gs/planner.py` |
| 控制 | 双向 Pure Pursuit、换挡停车、碰撞停止、终点误差统计 | `parking_gs/control.py` |
| 后端 | 场景列表、建图查询、异步任务队列、结果保存 | `parking_gs/server.py` |
| 前端 | 高斯预览、BEV 风险地图、交互起终点、回放、JSON 导出 | `frontend/` |
| 测试 | 几何、地图、COLMAP、规划、控制、HTTP 接口测试 | `tests/` |

## 当前交付状态

- **没有安装依赖、创建虚拟环境或下载数据集。** 依赖列在 `requirements.txt`。
- `data/raw/`、`data/processed/` 已保留；后续按 [数据文档](docs/02_DATASETS.md) 放置数据。
- 使用电脑已有 Python、NumPy、Pillow 执行核心测试，不改变现有环境。
- 合成场景、CPU A* 规划/控制、HTTP 接口已验证；GPU 前馈模型和 3DGS 训练代码未实际执行，因为当前未配置 PyTorch/CUDA/外部模型权重，也未提供真实视频。
- 详细验证结果见 [验证记录](docs/06_VALIDATION.md)。不要把程序生成场景的结果当作真实数据集性能。

## 后续运行

在项目根目录执行以下命令。当前交付阶段无需执行安装命令。

```powershell
# 后续由你配置：先选择匹配显卡/CUDA 的 PyTorch，再安装依赖
python -m pip install -r requirements.txt

# 启动浏览器实验台，默认合成场景直接在内存生成
python -m parking_gs.server
```

打开 <http://127.0.0.1:8080>。选择“合成停车场”，点击“生成路径并仿真”，任务完成后点击播放。也可执行 `scripts/run.ps1` 或 `scripts/run.sh`，它们只启动服务，不安装任何东西。

纯规划/可视化实际只需要 NumPy；视频重建另需 OpenCV 和 plyfile。PyTorch、gsplat 以及 DGGT/Splatt3R 自己的依赖只在执行前馈重建时使用。前端无 npm、无 CDN、无外部字体依赖。

## 视频到泊车的命令链

先下载并配置 DGGT 代码和权重（链接见 [视频前馈重建文档](docs/07_FEEDFORWARD_VIDEO.md)），把视频路径和模型路径替换成你的实际路径：

```powershell
python -m parking_gs.cli reconstruct-video --video data/raw/site/parking.mp4 --backend dggt --repo D:/src/dggt --checkpoint D:/weights/model_latest_waymo.pth --config configs/site.json --output outputs/video_site
python -m parking_gs.cli evaluate --scene outputs/video_site/scene.npz --output outputs/video_site/evaluation.json
python -m parking_gs.server
```

刷新前端，选择 `video_site` 场景；也可以直接在网页上传视频并填写 DGGT 路径。DGGT 需要 CUDA 和其官方权重。视频只生成静态场景的第一段窗口，动态物体会由 DGGT 的 dynamic confidence 过滤；系统不自动识别停车位、不自动估计当前车辆实时位姿，也不自动从 RGB 证明某区域可通行。

无需真实数据的复现：

```powershell
python -m parking_gs.cli demo
python -m parking_gs.cli evaluate --scene outputs/demo/scene.npz --ablation
python -m unittest discover -s tests -v
```

## 文档导航

1. [运行与目录说明](docs/01_QUICKSTART.md)
2. [数据集链接、目录及标定](docs/02_DATASETS.md)
3. [完整算法、坐标和实现说明](docs/03_ARCHITECTURE.md)
4. [前馈视频重建、模型安装与输出契约](docs/07_FEEDFORWARD_VIDEO.md)
5. [创新点、对照实验及研究边界](docs/04_INNOVATIONS.md)
5. [API、前端操作和扩展开发](docs/05_API_AND_DEVELOPMENT.md)
6. [验证记录与局限](docs/06_VALIDATION.md)
7. [开源依赖与参考资料](THIRD_PARTY_NOTICES.md)

原创项目代码按 MIT 许可提供。DGGT 按 Apache-2.0 使用；Splatt3R 为 CC BY-NC 4.0，仅建议用于非商业研究；两者代码和权重均不随本项目分发。参考文献、依赖许可证和项目创新范围均单独列出。
