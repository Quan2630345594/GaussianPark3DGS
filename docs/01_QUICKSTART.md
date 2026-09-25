# 运行与目录说明

## 1. 环境规划（本次不配置）

建议 Python 3.10–3.12。CPU Hybrid A* 演示与建图使用 NumPy；视频抽帧使用 OpenCV，PLY 读取使用 plyfile。旧的 per-scene 训练额外使用 PyTorch、CUDA、gsplat 1.5.3；DGGT/Splatt3R 另有各自环境。`requirements.txt` 是本项目基础依赖，不把外部模型仓库的 CUDA 扩展塞进来。

GPU 训练可选择 Linux 或 WSL2 环境；Windows 原生能否编译 gsplat 取决于 CUDA、PyTorch、编译工具组合。后续按 [PyTorch 安装页](https://pytorch.org/get-started/locally/) 与 [gsplat 官方仓库安装说明](https://github.com/nerfstudio-project/gsplat#installation) 选择匹配版本。不要默认系统里的 CUDA 版本与任意 pip torch 包匹配。COLMAP 是外部命令行工具，不属于 pip requirements；本次未安装。若已有带标定的 `dataset.json`，可以跳过 COLMAP。

视频前馈默认每 3 帧抽一帧、最多 96 帧、宽度 960，DGGT 单次窗口默认 8 帧。显存不足时先降 `--max-width 640 --max-frames 32 --sequence-length 4`。没有实测显存或帧率承诺。

## 2. 目录

```text
GaussianPark3DGS/
  README.md
  requirements.txt
  LICENSE
  THIRD_PARTY_NOTICES.md
  configs/site.json           # 必须按真实场地修改
  data/
    raw/                     # 你自行下载的数据，已保留
    processed/               # prepare 输出
  parking_gs/                # Python 核心代码及 CLI/HTTP 服务
  frontend/                  # 原生 HTML/CSS/JavaScript
  scripts/                   # 仅启动，不做环境安装
  tests/                     # 标准库 unittest 测试
  docs/                      # 完整中文文档
  outputs/
    demo/scene.npz           # 程序生成合成场景
    <video-job>/scene.npz    # 前馈视频产物
    runs/<任务ID>.json        # 前端运行保存
    evaluation.json         # CLI 实验结果
```

所有命令在工程根目录执行；服务静态资源路径由代码位置定位，不受终端当前目录影响。处理后的图像路径相对 `data/processed/site/` 保存，移动整个工程不需要改路径。

## 3. 演示

`python -m parking_gs.server` 启动本地 8080 端口。服务启动不会自动下载模型、权重或数据。合成场景在内存中生成，只是回归测试；真实流程从视频上传开始。如端口占用，执行 `python -m parking_gs.server --port 8081`。

在前端上传视频并完成前馈重建后，CPU 在后台线程中用占据图运行 Hybrid A*，再做闭环运动学仿真。结果回放不是在线车辆控制；它播放服务器计算出的轨迹，黄色为执行轨迹，绿色为计划轨迹。不同参数可能得到失败结果，这些结果不会伪装成成功动画。

## 4. 前馈视频重建

完整命令和 DGGT/Splatt3R 约束见 [07_FEEDFORWARD_VIDEO.md](07_FEEDFORWARD_VIDEO.md)。主命令为：

```powershell
# 已克隆主仓库的 submodule 时，DGGT 默认使用 third_party/dggt
python -m parking_gs.cli reconstruct-video --video data/raw/site/parking.mp4 --backend dggt --checkpoint D:/weights/model.pth --output outputs/video_site
```

## 5. 旧训练对照

```powershell
python -m parking_gs.cli train --data data/processed/site --output outputs/site --steps 3000 --max-points 40000 --max-width 960
```

训练每 50 步打印损失，每 500 步保存一次场景，结束后保存验证视角图像和 `reconstruction_metrics.json`。`training.json` 保存损失记录与随机种子。导出的 scene 是激活后的高斯参数，不含优化器状态，因此当前不提供断点续训；重新执行训练会从输入点云重新初始化并覆盖该输出目录中的同名训练产物。需要保留实验时使用不同输出目录。

## 6. 常见问题

| 现象 | 处理 |
|---|---|
| `No module named numpy` | 后续安装 requirements；当前工程未替你安装 |
| `training requires CUDA` | 旧训练和 DGGT/Splatt3R 前馈通常需要 CUDA；CPU 仍可运行已有 scene 的 A* 与可视化 |
| `Video reconstruction requires opencv-python` | 安装项目 requirements；当前不会替你安装 |
| `DGGT source not found` | 执行 `git submodule update --init --recursive`，或用 `--repo` 指定 DGGT checkout |
| `Feed-forward output must contain...` | 检查 bridge/外部命令是否输出全局对齐 scene.npz、Gaussian PLY 或规范 NPZ |
| 相机模型不支持 | 对图像执行 COLMAP image_undistorter，导出 PINHOLE 文本模型 |
| 起点/终点 blocked or unknown | 检查整个车身，不只是坐标点；检查已核验区域、米制尺度、地面坐标 |
| 搜索超时 | 增大通道、调整终点航向或起点；CLI/代码可调整搜索预算，HTTP 默认 25 秒 |
| 控制停止或终点误差超限 | 查看计划与执行偏差；缩小速度、调整控制器，不把此状态记为成功 |
| 已训练场景不在下拉框 | 确认在 `outputs/<名称>/scene.npz`，刷新页面；不要把真实场景命名为 demo |
| 预览较慢 | 浏览器只抽样显示最多 12,000 高斯；建图使用全部高斯 |

退出服务使用 Ctrl+C。当前任务会完成后退出，不提供训练/规划任务的强行终止接口。
