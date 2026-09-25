# 前馈视频重建：DGGT / Splatt3R

## 为什么默认选 DGGT

Splatt3R 官方仓库实现的是“未标定图像对 → 3D Gaussians”，适合两张有重叠的图片，不负责长视频的全局窗口对齐。DGGT 是面向驾驶场景的前馈 4D 重建，模型可以从未标定 RGB 序列预测相机位姿、深度和高斯图，并使用动态置信度筛静态内容。因此本项目的视频默认后端是 DGGT；Splatt3R 保留为图像对适配入口，必须由外部命令先完成全局对齐。

官方资料：

- [DGGT 官方仓库](https://github.com/xiaomi-research/dggt)：Apache-2.0，公开 `inference.py`，支持 Waymo、nuScenes、Argoverse2 的数据组织和预训练权重。
- [Splatt3R 官方仓库](https://github.com/btsmart/splatt3r)：CC BY-NC 4.0，官方 demo 输入一张或两张图片并输出 PLY；其 README 明确使用 MASt3R 相关 checkpoint。
- [Splatt3R 论文](https://arxiv.org/abs/2408.13912)。

DGGT 和 Splatt3R 源码现在作为 `third_party/` 下的 Git submodule 固定在主项目中；checkpoint、数据集和它们的独立运行环境仍不随本项目分发。已有主项目检出可执行 `git submodule update --init --recursive`。服务端不会自动执行 pip 或 Hugging Face 下载。

## DGGT 安装与运行

后续由你在 DGGT 的 submodule 或单独目录完成其环境配置。项目根目录只保留 `requirements.txt`，避免把 DGGT 的点操作 CUDA 扩展、数据集工具和本项目依赖混在同一环境中。

```powershell
# 如果主项目已用 --recurse-submodules 克隆，可直接使用 third_party/dggt
# 否则在主项目根目录执行：
git submodule update --init --recursive
# 按 DGGT README 创建它自己的环境并安装 requirements
# 按官方链接下载 Waymo checkpoint，例如 D:/weights/model_latest_waymo.pth

python -m parking_gs.cli reconstruct-video `
  --video data/raw/site/parking.mp4 `
  --backend dggt `
  --checkpoint D:/weights/model_latest_waymo.pth `
  --config configs/site.json `
  --output outputs/parking_video `
  --stride 3 --max-frames 96 --sequence-length 8
```

`scripts/dggt_export_scene.py` 会动态加入 `third_party/dggt`（也可通过 `--repo` 指定其他 checkout），加载 `dggt.models.vggt.VGGT`，读取前馈 checkpoint，调用深度和位姿转换，把静态高斯写成 `outputs/parking_video/scene.npz`。没有 submodule、权重、CUDA 或 `opencv-python` 时会立即给出错误，不会退回随机地图。

视频会先被抽帧为 JPG，默认每 3 帧取一帧、最多 96 帧、宽度最多 960。DGGT bridge 默认只处理第一段最多 8 帧，因为不同窗口的预测坐标系不能直接拼接。输出 `reconstruction.json` 会记录窗口限制、帧数和高斯数。如果要处理长视频，应在 DGGT 层做窗口间位姿/尺度对齐，再把对齐后的全局 `scene.npz` 交给本项目；当前版本拒绝把未对齐窗口静默合并。

## 米制坐标和占据地图

前馈模型的坐标尺度不一定等于停车场米制尺度。编辑 `configs/site.json`：

```json
{
  "metric_scale": 1.0,
  "world_rotation": [[1,0,0],[0,1,0],[0,0,1]],
  "world_translation": [0,0,0],
  "bounds": [-20,-20,20,20],
  "known_free_polygon": [[-20,-20],[20,-20],[20,20],[-20,20]],
  "start": [-8,0,0],
  "goal": [8,0,0],
  "slots": []
}
```

`metric_scale`、`world_rotation`、`world_translation` 会在加载前馈高斯后应用到位置和尺度。你需要用停车场的已知距离、地面方向和相机/车辆初始位置校准它们。`known_free_polygon` 只表示已检查过的区域；多边形外全部视为未知，不会因为地图没有高斯就开放通行。高斯投影、透明度和高度过滤随后生成 risk/known 占据栅格。

如果只有视频而没有车位坐标，项目不会自动猜测目标车位。可在网页左侧修改起点/终点，或在 config 中填写 `slots` 用于可视化。视频重建阶段默认不识别车位，也不做在线车辆定位。

## Splatt3R 适配

Splatt3R 只产生图像对的局部高斯。用它处理视频时，外部脚本必须：抽取重叠图像对、执行模型、估计每对之间的全局相似变换、合并并写出一个全局 PLY 或 NPZ。然后：

```powershell
python -m parking_gs.cli reconstruct-video `
  --video data/raw/site/parking.mp4 `
  --backend splatt3r `
  --repo third_party/splatt3r `
  --checkpoint D:/weights/epoch=19-step=1200.ckpt `
  --command "python D:/tools/my_splatt3r_video.py --frames {frames} --output {output} --checkpoint {checkpoint}" `
  --output outputs/parking_splatt3r
```

命令必须在 `{output}` 目录生成 `scene.npz`、一个 Gaussian PLY，或包含 `means/points`、`scales`、`quats/rotation`、`colors/rgbs`、`opacities/opacity` 的 NPZ。解析器支持常见 Graphdeco PLY 字段：`x/y/z`、`red/green/blue` 或 `f_dc_*`、`opacity`、`scale_*`、`rot_*`。如果输出多个未对齐 PLY，适配器不会替你假定它们处于同一坐标系。

Splatt3R 的 CC BY-NC 4.0 限制意味着不能把该模型、其权重或其改编运行时用于商业分发。DGGT 为 Apache-2.0，但它自己的 checkpoint、数据集许可和依赖仍需按上游要求处理。

## Web 操作

启动 `python -m parking_gs.server`，浏览器打开 `http://127.0.0.1:8080`：选择前馈后端，DGGT 的 repo 留空时使用 `third_party/dggt`，再填写 checkpoint，选择视频并点“视频重建并刷新地图”。服务把视频保存到 `outputs/<job-id>/input.*`，抽帧与模型日志保存在同一目录，成功后自动出现在场景列表。再编辑起点/终点，点击“Hybrid A* 生成路径并仿真”。

前端展示：高斯场景、鸟瞰 risk/known 地图、Hybrid A* 路径、控制轨迹、展开节点数和误差。失败任务会显示后端错误或“无 Hybrid A* 路径”，不会展示预设路径冒充真实结果。

## 真实数据限制

DGGT 官方推理脚本依赖其自己的 Waymo-style 数据加载器，普通手机视频的域差异、动态目标、曝光变化和尺度漂移都可能造成错误高斯。当前 bridge 是研究适配层，不是已验证的手机视频产品。对真实泊车实验，请先用独立测量的障碍/地面真值检查 risk 图，再运行 A*；不要将可视化结果当作实车安全保证。
