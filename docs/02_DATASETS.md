# 数据集、放置目录与标定

## 1. 下载入口

本次没有下载数据或模型。以下是官方入口，访问时间 2026-09-12；注册、许可同意、分卷下载由你在官网完成。

| 数据来源 | 官方链接 | 放置目录 | 在本项目中的作用 |
|---|---|---|---|
| KITTI-360 | https://www.cvlibs.net/datasets/kitti-360/download.php | `data/raw/kitti360/` | 城市场景多视角重建实验，选择静态停车场附近的透视相机片段 |
| KITTI Odometry | https://www.cvlibs.net/datasets/kitti/eval_odometry.php | `data/raw/kitti_odometry/` | 有标定的序列，适合验证重建链路；不保证含泊车任务 |
| 自采停车场数据 | 你自己的图片/视频与测量数据 | `data/raw/site/images/` | 最适合完整泊车演示，可确定米制尺度、地面和停车位 |

KITTI-360 数据组织与相机说明：https://www.cvlibs.net/datasets/kitti-360/documentation.php 。数据集中提供哪些图像、位姿和标注，以官网下载页为准。KITTI 系列不是现成的“泊车控制监督数据集”。项目不假设其自带本项目需要的目标车位和可行驶区域。

**默认视频路径不再依赖 COLMAP：** `parking_gs/feedforward.py` 从视频抽帧并调用 DGGT bridge；COLMAP PINHOLE 文本模型适配器仍作为旧训练/对照路径保留。KITTI-360 原生位姿/鱼眼适配器尚未实现。最直接的前馈路径是把一段静态停车场视频交给 DGGT；如果走旧路径，再从公开序列选出透视图像，经 COLMAP 重建与去畸变后导入。本项目不会自动解压和猜测官网数据层级，也不会把不同序列/相机图片直接混成一个未标定场景。

## 2. 保留目录

```text
data/raw/
  kitti360/                 # 自行下载后放这里
  kitti_odometry/           # 自行下载后放这里
  site/
    images/                # 选取/自采图片
    sparse/                # COLMAP mapper 输出
    undistorted/
      images/
      sparse/
    colmap_text/
      cameras.txt
      images.txt
      points3D.txt
data/processed/
  site/
    dataset.json
    points.npz
```

文件夹只保留空占位；无需同时下载两套 KITTI 数据。自采静态停车场即可走完整流程。视频可自行抽帧，需保证相邻图像有足够重叠和视差。避免把大量行人、行驶车辆作为静态重建几何。

## 3. 外部 COLMAP 预处理

先在未来配置 COLMAP，再执行以下示例。`mkdir` 对应创建文件夹；这些命令本次没有执行。

```powershell
New-Item -ItemType Directory -Force data/raw/site/sparse, data/raw/site/undistorted, data/raw/site/colmap_text
colmap feature_extractor --database_path data/raw/site/database.db --image_path data/raw/site/images --ImageReader.single_camera 1
colmap sequential_matcher --database_path data/raw/site/database.db
colmap mapper --database_path data/raw/site/database.db --image_path data/raw/site/images --output_path data/raw/site/sparse
colmap image_undistorter --image_path data/raw/site/images --input_path data/raw/site/sparse/0 --output_path data/raw/site/undistorted --output_type COLMAP
colmap model_converter --input_path data/raw/site/undistorted/sparse --output_path data/raw/site/colmap_text --output_type TXT
```

示例假设固定内参的单相机连续序列。若图像来自不同相机，不使用 single_camera 1；若不是顺序序列，可选择 exhaustive_matcher。mapper 可能产生多个子模型，需要选取覆盖目标停车场的那个，示例使用 `0`。

模型格式官方说明：https://colmap.github.io/format.html 。适配器读取每张图像的 world-to-camera 四元数和平移，再求相机中心与 camera-to-world。仅接受 PINHOLE/SIMPLE_PINHOLE；不会把未去畸变图像当作针孔图像处理。

## 4. 关键：米制尺度和地面方向

单目 SfM 的尺度不确定。`configs/site.json` 中默认的 1.0 和单位旋转只是模板，不能直接当作真实场地标定。

1. 在重建点云中选两个有已知实测距离的点，计算 `scale = 实测米数 / 重建距离`。
2. 确定地面平面，构造将地面法线转到 +Z 的正交旋转 `world_rotation`。也可以使用已标定外部位姿，但需转成相同坐标定义。
3. 用 `world_translation` 把地面移至 z=0，并把场地放入合理局部坐标范围。
4. 变换公式：`X_metric = scale * R * X_colmap + t`。相机旋转为 `R * R_camera_to_colmap`，相机位置使用相同尺度和平移。
5. 修改 bounds `[xmin,ymin,xmax,ymax]`、start/goal `[x,y,yaw]`，yaw 使用弧度。车辆位姿是**后轴中心**；停车位 x/y 是车位几何中心，两者通常不同。
6. `known_free_polygon` 填入按顺序排列的已核验区域顶点。这里表示“已调查、可对障碍风险作判断的区域”，并不抹除其中的高斯障碍。没有填写时整张地图保持未知并拒绝规划。不能仅凭没有高斯就把空间设为空闲。

当前以人工核验多边形作为自由空间先验，不包含深度射线融合、在线可见性推理、可行驶区域分割。对真实数据必须核对该区域内是否有重建遗漏的障碍。

## 5. 直接提供标准数据

也可绕过 COLMAP，自行生成 `data/processed/site/dataset.json` 与 `points.npz`。

```json
{
  "points": "points.npz",
  "metadata": {
    "units": "meters", "up_axis": "z", "source": "calibrated_capture",
    "bounds": [-12,-8,12,8],
    "start": [-8,1,0], "goal": [-1.5,-5.3,1.57079632679],
    "known_free_polygon": [], "slots": []
  },
  "frames": [
    {
      "image": "../../raw/site/undistorted/images/000001.png",
      "width": 1280, "height": 720,
      "K": [[900,0,640],[0,900,360],[0,0,1]],
      "c2w": [[1,0,0,0],[0,1,0,0],[0,0,1,1],[0,0,0,1]]
    }
  ]
}
```

上述只有一帧用于说明结构，实际至少三帧。K 为去畸变图像内参；相机坐标使用 OpenCV：右 X、下 Y、前 Z；世界坐标使用 Z 向上。示例矩阵仅为格式示意，不代表相机正确朝向地面。

`points.npz` 包含 `points: float[N,3]` 与 `colors: float[N,3]`，颜色 0–1。可在每帧增加 `"depth":"depth/000001.npy"`，其内容是原图大小的**相机 Z 深度、单位米**，不是欧氏距离，也不是逆深度；无效值为 0 或 NaN。训练会同步缩放图像和 K，用最近邻缩放深度。RGB-only 数据不需要 depth 字段。

帧序号 0、8、16……划为验证集，其余训练。这个固定抽样可复现，但邻帧强相关；论文级实验应进一步做时段/视角隔离划分，不能把该 PSNR 直接解释为跨场景泛化能力。
