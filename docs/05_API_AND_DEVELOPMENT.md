# API 与扩展接口

## 1. 服务

~~~powershell
python -m parking_gs.server --host 127.0.0.1 --port 8080
~~~

服务基于标准库 ThreadingHTTPServer，默认只监听本机。规划任务在后台线程执行，队列容量有限；接口用于实验复现，不面向生产部署。

## 2. HTTP 接口

| 方法 | 路径 | 语义 |
|---|---|---|
| GET | /api/health | 服务状态 |
| GET | /api/scenes | 可用 scene.npz |
| GET | /api/scene?id=demo | 场景与高斯属性 |
| GET | /api/grid?id=demo | 风险、known 与地图参数 |
| POST | /api/jobs | 已有场景的规划与仿真 |
| POST | /api/reconstruct | 视频前馈重建 |
| GET | /api/jobs/<id> | 异步任务状态与结果 |

规划请求的核心字段如下：

~~~json
{
  "scene": "demo",
  "start": [-8, 1, 0],
  "goal": [-1.5, -5.3, 1.5708],
  "uncertainty": 0.12,
  "planner": "hybrid"
}
~~~

start 与 goal 为后轴中心的米制位姿，航向单位为弧度。planner 默认 hybrid，可选 astar。返回值包含地图参数、path、expanded、seconds、仿真 status、终点误差、行驶距离、换挡次数及完整 trace。

视频重建使用 multipart 字段 video、backend、repo、checkpoint、command、config、stride、max_frames、max_width 和 sequence_length。DGGT 默认使用 third_party/dggt；Splatt3R 或 external 需要 command 写出全局对齐的 scene.npz、Gaussian PLY 或规范 NPZ。

## 3. Python 扩展

核心流程不依赖 Web：

~~~python
from parking_gs.scene import Scene
from parking_gs.mapping import build_grid
from parking_gs.planner import plan, Vehicle
from parking_gs.control import simulate

scene = Scene.load("outputs/site/scene.npz")
grid = build_grid(scene, resolution=0.25, uncertainty=0.12)
result = plan(scene.metadata["start"], scene.metadata["goal"], grid, Vehicle())
simulation = simulate(result, grid, speed=0.65)
~~~

新增重建后端只需输出统一场景字段；新增场景保存为 outputs/<id>/scene.npz 即可被服务发现。规划器和控制器均可脱离 HTTP 单独调用。

## 4. 验证

~~~powershell
python -m unittest discover -s tests -v
python -m compileall -q parking_gs scripts tests
node --check frontend/app.js
~~~

测试使用合成场景、临时文件和本地端口，不代表真实数据性能。