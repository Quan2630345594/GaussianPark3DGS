# API 与开发说明

## 1. 服务

`python -m parking_gs.server --host 127.0.0.1 --port 8080`。

后端为标准库 ThreadingHTTPServer，规划使用一个后台工作线程，最多容纳四个运行/排队任务。默认仅监听本机，未提供认证和生产级部署机制；无 shell 执行、任意文件读取或在线安装接口。前端资源来自同一服务，无跨域配置需求。

## 2. 接口

| 方法与路径 | 返回 |
|---|---|
| GET `/api/health` | 服务状态与版本 |
| GET `/api/scenes` | demo 与 outputs 子目录中的 scene.npz 列表 |
| GET `/api/scene?id=demo` | means、covariance、colors、opacities、metadata、总数/显示数 |
| GET `/api/grid?id=demo` | 默认参数风险图、known、bounds、resolution、threshold |
| POST `/api/jobs` | HTTP 202，使用已有 scene 的 A* 规划任务 |
| POST `/api/reconstruct` | HTTP 202，multipart 视频前馈重建任务 |
| GET `/api/jobs/<id>` | queued / running / done / failed 与结果/错误 |

创建任务（默认 Hybrid A*；只有需要传统栅格对照时才传 `"planner":"astar"`）：

```json
{
  "scene": "demo",
  "start": [-8,1,0],
  "goal": [-1.5,-5.3,1.57079632679],
  "uncertainty": 0.12,
  "planner": "hybrid"
}
```

start/goal 为后轴中心米制位姿，HTTP 航向单位为弧度，前端输入使用角度并自动转换。scene 必须来自列表，不能通过路径越界读取。uncertainty 允许 0–0.6 m。请求 JSON 上限 8192 字节，队列满返回 429。

完成后的 `result`：

```text
scene, uncertainty
grid: risk[H][W], known[H][W], bounds, resolution, threshold
plan:
  path: [{x,y,yaw,direction,steer}, ...]
  goal, vehicle, expanded, seconds, position_error, yaw_error
simulation:
  status: parked | collision_stop | timeout | terminal_error
  trace: [{x,y,yaw,speed,steer,t}, ...]
  metrics: position_error_m, yaw_error_rad, travel_m, gear_switches, duration_s
```

`POST /api/reconstruct` 的 multipart 字段为 `video`、`backend`、`repo`、`checkpoint`、`command`（Splatt3R/external 可选）、`config`（JSON 字符串）、`stride`、`max_frames`、`max_width`、`sequence_length`。DGGT 必须提供 repo 和 checkpoint；Splatt3R/external 的 command 必须使用 `{frames}` 与 `{output}` 占位符，并写出一个全局对齐的 scene.npz/PLY/NPZ。上传视频限制 1 GiB，扩展名限制 mp4/mov/avi/mkv/webm。

重建任务完成后，`result.scene` 是可直接传给 `/api/scene?id=...` 与 `/api/jobs` 的场景 ID；输出目录包含抽帧、feedforward.log、reconstruction.json 和 scene.npz。

HTTP job 的 done 表示计算完成，不意味着泊车成功；泊车是否成功读取 `result.simulation.status`。每次成功完成计算的 payload 保存到 `outputs/runs/<id>.json`，失败异常在任务状态中返回。内存只保留最近的一批已完成响应，旧任务查询可能返回 404，磁盘结果仍保留。服务重启不恢复队列或旧任务 id 查询。

## 3. 前端

- 3D：拖动旋转，滚轮缩放；高斯按深度混合，路径与车辆为调试覆盖层。
- BEV：颜色显示风险，灰色是未知区域；点击设置终点，Shift 点击设置起点。
- 左侧：编辑起终点、航向和几何膨胀；任务运行期间禁止修改任务参数。
- 回放：播放/暂停、时间轴、1×/2×/4×速度。
- 导出：下载完整任务结果 JSON，与服务端保存结构一致。

首次加载展示默认 0.12 m 的地图；调整滑块后，新的风险图在提交任务并完成计算后更新。网页会清除旧轨迹，避免把旧结果当作新参数结果。

## 4. 扩展接口

核心函数不依赖 Web：

```python
from parking_gs.scene import Scene
from parking_gs.mapping import build_grid
from parking_gs.planner import plan, Vehicle
from parking_gs.control import simulate

scene = Scene.load('outputs/site/scene.npz')
grid = build_grid(scene, resolution=0.25, uncertainty=0.12)
result = plan(scene.metadata['start'], scene.metadata['goal'], grid, Vehicle())
simulation = simulate(result, grid, speed=0.65)
```

修改车辆参数时同时使用 result 中的 vehicle 传递给控制器；不要只改前端画框。新增前馈场景保持 `outputs/<id>/scene.npz` 约定即可被发现。Hybrid A* 已包含自行车运动学和前进/倒车搜索，但仍不包含真实执行器延迟、轮胎侧滑和动力学约束。

API 不提供 per-scene 训练任务启动；旧训练通过 CLI 执行，日志写入输出目录。前馈视频重建通过 API/CLI 执行。模型代码/权重不会由 API 下载。图像抽帧由项目完成，场地尺度、已知区域和起终点仍需配置。

## 5. 测试

```powershell
python -m unittest discover -s tests -v
# 如果已配置 pytest，也可 python -m pytest tests -q
# Node 仅用于可选的 JS 语法检查，不是前端运行依赖
node --check frontend/app.js
```

测试使用临时文件和本地临时端口。不会下载数据或启动 GPU 训练。主流程测试通过合成场景验证整个车辆轮廓与控制轨迹；真实世界性能必须另做数据实验。
