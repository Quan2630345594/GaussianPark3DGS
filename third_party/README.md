# External model submodules

This directory pins the source repositories used by the optional feed-forward
reconstruction backends:

- `dggt/` — the default video backend.
- `splatt3r/` — the optional image-pair backend.

Clone the project with its submodules:

```powershell
git clone --recurse-submodules https://github.com/Quan2630345594/GaussianPark3DGS.git
```

For an existing checkout, initialize them with:

```powershell
git submodule update --init --recursive
```

Model checkpoints, CUDA environments, datasets, and generated outputs are not
stored in Git. The DGGT CLI uses `third_party/dggt` by default; pass `--repo`
when using another checkout. Splatt3R still requires a user-provided command
that globally aligns its pairwise outputs before writing one scene artifact.
