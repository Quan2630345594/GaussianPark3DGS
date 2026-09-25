# 外部模型 submodule

third_party/dggt 为默认视频前馈后端，third_party/splatt3r 为可选图像对后端。源码由 .gitmodules 固定，模型权重、数据集和 CUDA 环境外置。

~~~powershell
git clone --recurse-submodules https://github.com/Quan2630345594/GaussianPark3DGS.git
~~~

已有检出执行：

~~~powershell
git submodule update --init --recursive
~~~

DGGT CLI 默认读取 third_party/dggt；Splatt3R 需要外部命令完成图像对的全局对齐并输出统一场景。