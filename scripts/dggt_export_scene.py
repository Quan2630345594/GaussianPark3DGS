"""DGGT bridge: run the public model and export the project Scene NPZ.

This file intentionally keeps DGGT out of the main package.  Put a checkout of
https://github.com/xiaomi-research/dggt and its checkpoint on disk, then the
main project invokes this bridge.  No weights are downloaded automatically.
"""
import argparse
from pathlib import Path
import sys
import numpy as np


def load_images(paths, size=518):
    import torch
    from PIL import Image
    tensors = []
    for path in paths:
        image = Image.open(path).convert('RGB')
        w, h = image.size
        new_h = round(h * (size / w) / 14) * 14
        image = image.resize((size, new_h), Image.Resampling.BICUBIC)
        tensor = torch.from_numpy(np.asarray(image)).permute(2, 0, 1).float() / 255.
        if new_h > size:
            top = (new_h - size) // 2
            tensor = tensor[:, top:top + size]
        tensors.append(tensor)
    return torch.stack(tensors)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dggt-repo', required=True)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--frames', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--sequence-length', type=int, default=8)
    args = parser.parse_args()
    repo = Path(args.dggt_repo).resolve()
    if not (repo / 'dggt').is_dir():
        raise SystemExit('DGGT repo must contain the dggt/ package')
    sys.path.insert(0, str(repo))
    import torch
    from dggt.models.vggt import VGGT
    from dggt.utils.pose_enc import pose_encoding_to_extri_intri
    from dggt.utils.geometry import unproject_depth_map_to_point_map
    from dggt.utils.gs import get_split_gs

    paths = sorted(Path(args.frames).glob('*.jpg'))
    if len(paths) < 2:
        raise SystemExit('DGGT bridge requires at least two extracted frames')
    if args.sequence_length < 2:
        raise SystemExit('--sequence-length must be >= 2')
    # Long videos are processed in overlapping windows. DGGT predicts a global
    # coordinate frame for each window; we retain the first window here and
    # expose the limitation instead of silently concatenating incompatible maps.
    paths = paths[:args.sequence_length]
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    images = load_images(paths).to(device)
    model = VGGT().to(device)
    checkpoint = torch.load(args.checkpoint, map_location='cpu')
    if isinstance(checkpoint, dict) and 'state_dict' in checkpoint:
        checkpoint = checkpoint['state_dict']
    model.load_state_dict(checkpoint, strict=True)
    model.eval()
    with torch.no_grad():
        pred = model(images[None])
        h, w = images.shape[-2:]
        extrinsics, intrinsics = pose_encoding_to_extri_intri(pred['pose_enc'], (h, w))
        # DGGT's public inference path uses its depth head plus predicted poses
        # to put each pixel into the predicted world frame.
        point_map = unproject_depth_map_to_point_map(pred['depth'][0], extrinsics[0], intrinsics[0])
        if not torch.is_tensor(point_map):
            point_map = torch.as_tensor(point_map, device=device)
        point_map = point_map[None, ...]
        gs_map = pred['gs_map']
        dynamic = pred.get('dynamic_conf')
        if dynamic is None:
            dynamic = torch.zeros(gs_map.shape[:-1] + (1,), device=device)
        dynamic = dynamic.squeeze(-1)
        mask = dynamic < .5
        # Very low confidence points are removed before serialization.
        confidence = pred.get('gs_conf')
        if confidence is not None:
            mask = mask & (confidence > confidence.median())
        rgbs, opacity, scales, rotation = get_split_gs(gs_map, mask)
        points = point_map[mask].reshape(-1, 3)
        count = min(250_000, len(points))
        if count == 0:
            raise SystemExit('DGGT produced no static Gaussian points')
        if len(points) > count:
            scores = opacity.detach().float().flatten()
            keep = torch.topk(scores, count).indices
            points, rgbs, opacity, scales, rotation = [x[keep] for x in (points, rgbs, opacity, scales, rotation)]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(output, means=points.detach().cpu().numpy(),
                        colors=rgbs.detach().cpu().numpy(),
                        opacities=opacity.detach().cpu().numpy().reshape(-1),
                        scales=scales.detach().cpu().numpy(),
                        quats=rotation.detach().cpu().numpy())
    print(f'Exported {count} static DGGT Gaussians to {output}')


if __name__ == '__main__':
    main()
