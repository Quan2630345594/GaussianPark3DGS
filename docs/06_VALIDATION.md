# 交付验证记录

验证日期：2026-09-25。使用电脑已有 Python 3.12.7、NumPy、Pillow、Node 24.15.0 与 Microsoft Edge。未执行 pip/conda/npm 安装，未创建项目虚拟环境，未下载数据集或前馈模型权重。

## 已执行

1. `python -m unittest discover -s tests -v`：15 项测试全部通过，覆盖场景保存读取、未知区域与越界、车身内部细障碍、传统 A* 对照、Hybrid A* 倒车规划控制、旋转协方差、地面过滤、COLMAP 米制转换、前馈 NPZ 契约、历史合成泊车、HTTP 校验及任务生命周期。
2. `node --check frontend/app.js`：JavaScript 语法检查。
3. `python -m parking_gs.cli demo`：生成 4,136 个高斯的程序场景，仅用于回归测试。
4. `python -m parking_gs.cli evaluate --scene outputs/demo/scene.npz --ablation`：验证 Hybrid A* API 和两种地图核函数；demo 不是视频重建。
5. 启动本地 HTTP 服务，用 Edge 无窗口模式加载页面并截图。确认中文排版、场景加载、高斯预览、参数区与回放区显示正常。截图见 `outputs/frontend-preview.png`。没有把静态截图检查说成所有按钮的浏览器自动化覆盖；HTTP 任务链路由接口测试覆盖。

## 合成演示结果

起点 `[-8,1,0]`，目标后轴位姿 `[-1.5,-5.3,π/2]`。结果保存在 `outputs/evaluation.json`。

| 指标 | covariance | centers |
|---|---:|---:|
| 状态 | parked | parked |
| 终点位置误差 | 0.10527 m | 0.10527 m |
| 终点航向误差 | 0.05265 rad | 0.05265 rad |
| 行驶距离 | 14.68234 m | 14.68234 m |
| 换挡次数 | 1 | 1 |
| 仿真时长 | 24.5 s | 24.5 s |
| 完整协方差参考地图碰撞 | false | false |

上述默认场景两种方法得到相同路径与控制结果，**没有观察到创新方案的性能优势**。这说明演示任务可以贯通，不足以证明方法提升。规划墙钟耗时受机器负载影响，具体每次耗时保留在 JSON 的 plan.seconds 中，不作为固定性能保证。

## 未验证

- PyTorch/CUDA/gsplat 的安装、编译和 GPU 训练执行。
- 真实数据集的重建质量、深度精度、停车成功率、独立几何碰撞率。
- 不同设备的浏览器帧率与显存需求。
- CARLA、ROS2、实车通讯、传感器同步、在线定位、动态障碍和执行器动力学。

DGGT bridge、视频抽帧和前馈 artifact 解析已通过 Python 编译检查，但没有外部 checkpoint，因此没有执行真实前馈推理。后续建议先对 8 帧小视频运行 bridge，检查 `scene.npz`、米制 bounds 和占据图，再开展 A* 实验。旧训练实现也只通过语法/接口检查，不能替代 GPU 实测。
