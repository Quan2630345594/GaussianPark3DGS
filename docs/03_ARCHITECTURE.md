# 系统方法

## 1. 问题定义

给定 RGB 视频 V、前馈重建模型 f、车辆参数 θ 和米制场地先验 Ω，系统计算

S = f(V),   G = M(S, Ω),   τ = H(G, θ),   ξ = C(τ, G, θ)。

其中 S 为 3D Gaussian 场景，G 为风险与未知区域地图，H 为 Hybrid A*，C 为闭环运动学仿真。输出包括场景、规划轨迹、执行轨迹和误差指标。

~~~mermaid
flowchart LR
 A[RGB video] --> B[feed-forward reconstruction]
 B --> C[metric Gaussian scene]
 C --> D[occupancy risk map]
 D --> E[Hybrid A*]
 E --> F[closed-loop simulation]
 C --> G[3D/BEV visualization]
 D --> G
 F --> G
~~~

程序生成的 scene 仅用于验证 S→G→τ→ξ 的软件链路，不代表真实视频重建。

## 2. 前馈重建

feedforward.py 完成视频抽帧、模型进程隔离和输出归一化。默认 bridge 将 third_party/dggt 动态加入 Python 路径，读取 VGGT checkpoint，并导出包含均值、尺度、四元数、颜色和透明度的 scene.npz。Splatt3R 通过外部命令接入，要求不同图像对先变换到统一世界坐标。

DGGT bridge 当前处理首个 sequence_length 窗口；长视频的窗口融合与尺度对齐属于后续工作。模型源码以 submodule 管理，权重不纳入版本库。

## 3. 场景与坐标

场景单位为米，世界 Z 轴向上，地面为 z=0；相机采用 OpenCV X 右、Y 下、Z 前。车辆状态为后轴中心位姿 [x,y,yaw]，yaw 为弧度。车辆模型采用轴距 2.65 m、宽 1.8 m、前后悬约 3.55/0.9 m。

每个高斯由均值 μ、尺度 s、四元数 q、颜色 c 和透明度 α 表示。旋转协方差为 Σ = R(q) diag(s²) R(q)ᵀ。scene.npz 保存激活后的正尺度、颜色和透明度，不等同于 Graphdeco PLY 的 log-scale/SH 表示。

## 4. 占据风险图

首先按高斯的 Z 支撑范围与碰撞高度层 [0.15, 2.0] m 进行过滤。对保留高斯取 XY 协方差边缘并加入几何膨胀 u 与栅格项：

C_i = Σ_i[0:2,0:2] + (u² + Δ²/4)I，

r(x) = max_i α_i exp[-1/2 (x-μ_i)ᵀ C_i⁻¹ (x-μ_i)]。

风险图是几何启发式分数，不是校准后的占据概率。known 掩码由人工核验多边形提供，unknown 区域禁止规划。默认分辨率为 0.25 m，风险阈值为 0.35，膨胀为 0.12 m。

## 5. Hybrid A* 与控制

状态为 (x,y,yaw)，节点键还包含行驶方向和转向档位。扩展采用自行车运动学，枚举前进/倒车及离散转角，并在积分子步检查完整车辆轮廓。代价包含路径长度、倒车、换挡、转向变化与风险项；搜索同时尝试 LSL、RSR、LSR、RSL 等 CSC 连接。

Pure Pursuit 根据执行位姿跟踪带方向的轨迹，换挡时插入零速状态。每一步复用同一碰撞判定；发生碰撞或越界则停止并返回失败状态。规划与仿真不包含轮胎侧滑、执行器延迟、动态障碍或在线定位。

## 6. 前端与接口

前端以 Canvas 近似渲染带协方差高斯，并显示 BEV 风险图、计划轨迹和执行轨迹。显示层最多抽样 12,000 个高斯，规划使用全量场景。HTTP 服务提供场景、地图、规划任务和视频重建任务接口；API 详见 API 文档。