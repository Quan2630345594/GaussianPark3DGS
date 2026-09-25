# 数据与坐标标定

## 数据来源

| 数据 | 官方入口 | 目录 | 适用实验 |
|---|---|---|---|
| KITTI-360 | https://www.cvlibs.net/datasets/kitti-360/download.php | data/raw/kitti360 | 多视角场景重建 |
| KITTI Odometry | https://www.cvlibs.net/datasets/kitti/eval_odometry.php | data/raw/kitti_odometry | 带标定序列验证 |
| 自采停车场 | 用户视频、图像与测量 | data/raw/site | 完整泊车实验 |

KITTI 不是泊车控制监督数据集，目标车位和可行驶区域需独立定义。前馈视频路径不要求 COLMAP；COLMAP 仅服务于旧的图像重建基线。

## 输入契约

标准数据集由 dataset.json 与 points.npz 构成：

~~~json
{
  "points": "points.npz",
  "metadata": {
    "units": "meters",
    "up_axis": "z",
    "bounds": [-12,-8,12,8],
    "start": [-8,1,0],
    "goal": [-1.5,-5.3,1.5708],
    "known_free_polygon": [],
    "slots": []
  },
  "frames": [
    {"image": "...", "width": 1280, "height": 720,
     "K": [[900,0,640],[0,900,360],[0,0,1]],
     "c2w": [[1,0,0,0],[0,1,0,0],[0,0,1,1],[0,0,0,1]]}
  ]
}
~~~

points.npz 至少包含 points[N,3] 与 colors[N,3]；深度为相机 Z 深度，单位为米。相机采用 OpenCV 坐标约定，世界坐标 Z 轴向上。

## COLMAP 基线

连续图像可按 COLMAP 官方格式完成特征提取、匹配、建图、去畸变和 TXT 导出；适配器支持 PINHOLE 与 SIMPLE_PINHOLE。模型格式见 https://colmap.github.io/format.html。不同相机或鱼眼图像不应直接混用。

## 米制变换

单目重建的尺度和方向不确定。给定重建坐标 X、尺度 s、旋转 R 与平移 t：

X_metric = s R X + t。

应使用实测距离估计 s，使用地面法向确定 R，并令地面位于 z=0。随后配置 bounds、start、goal 与 known_free_polygon。known_free_polygon 表示已核验区域；其外部空间保持 unknown，不因缺少高斯而视为空闲。

## 实验划分

固定抽样可用于软件回归，但相邻帧相关性较强。正式实验应按场景或时间段划分训练、验证和测试，并报告重建质量、占据误差、规划成功率、独立几何碰撞率和终点误差。