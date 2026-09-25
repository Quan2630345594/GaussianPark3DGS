# 前馈视频重建

## 1. 模型选择

DGGT 面向驾驶场景的 RGB 序列，可预测相机位姿、深度与高斯场，因此作为默认视频后端。Splatt3R 主要处理未标定图像对，适合作为可选适配器；长视频需要额外的全局位姿对齐。

- DGGT：https://github.com/xiaomi-research/dggt，Apache-2.0。
- Splatt3R：https://github.com/btsmart/splatt3r，CC BY-NC 4.0。
- Splatt3R 论文：https://arxiv.org/abs/2408.13912。

两者源码已固定在 third_party/；checkpoint、数据集和模型环境不纳入版本库。

## 2. DGGT 流程

~~~powershell
git submodule update --init --recursive
python -m parking_gs.cli reconstruct-video --video data/raw/site/parking.mp4 --backend dggt --checkpoint D:/weights/model.pth --config configs/site.json --output outputs/parking_video
~~~

默认源码路径为 third_party/dggt，可用 repo 参数覆盖。bridge 读取连续帧，调用 VGGT 推理，并导出 scene.npz。当前默认只处理首个 sequence_length 窗口；不同窗口的坐标系未自动融合。

## 3. 输出契约

输出场景至少包含：

- means 或 points：N×3 世界坐标；
- scales：N×3 正尺度；
- quats 或 rotations：N×4；
- colors 或 rgbs：N×3，范围 0–1；
- opacities 或 opacity：N。

支持规范 NPZ、Gaussian PLY 和 DGGT bridge 生成的 scene.npz。随后系统应用 metric_scale、world_rotation 和 world_translation，并由高斯生成风险/known 地图。

## 4. Splatt3R 适配

外部命令需要完成图像对抽取、全局相似变换和高斯合并，最终写出一个全局对齐的 PLY 或 NPZ：

~~~powershell
python -m parking_gs.cli reconstruct-video --video data/raw/site/parking.mp4 --backend splatt3r --repo third_party/splatt3r --checkpoint D:/weights/model.ckpt --command "python tools/video_adapter.py --frames {frames} --output {output} --checkpoint {checkpoint}" --output outputs/parking_splatt3r
~~~

局部 PLY 不得直接拼接；坐标未对齐时输出不具有统一地图意义。

## 5. 尺度与限制

metric_scale 由已知距离标定，world_rotation 使地面法向对齐 +Z，world_translation 将地面置于 z=0。known_free_polygon 描述已核验区域，其外部保持 unknown。

普通手机视频与 DGGT 训练域可能存在显著差异，动态物体、曝光变化和尺度漂移会影响几何质量。当前适配器是研究接口，不是经过真实泊车验证的产品。