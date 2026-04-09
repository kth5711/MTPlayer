from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
import os

from .media_common import _first_float


def _torchcodec_imports():
    try:
        import torch  # type: ignore
        from torchcodec.decoders import VideoDecoder  # type: ignore
        try:
            from torchcodec.decoders import set_cuda_backend  # type: ignore
        except ImportError:
            set_cuda_backend = None
        try:
            from torchcodec.transforms import Resize as TorchCodecResize  # type: ignore
        except ImportError:
            TorchCodecResize = None
    except Exception:
        return None
    return torch, VideoDecoder, set_cuda_backend, TorchCodecResize


def _torchcodec_device(torch, prefer_gpu: bool) -> str:
    if not bool(prefer_gpu):
        return "cpu"
    try:
        if not bool(torch.cuda.is_available()):
            return "cpu"
        try:
            cur = int(torch.cuda.current_device())
        except (AttributeError, RuntimeError, TypeError, ValueError):
            cur = 0
        return f"cuda:{max(0, cur)}"
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return "cpu"


def _torchcodec_resize_transforms(resize_dims, resize_cls):
    try:
        if resize_dims is None or resize_cls is None:
            return None
        target_h, target_w = resize_dims
        if int(target_h) <= 0 or int(target_w) <= 0:
            return None
        return [resize_cls((int(target_h), int(target_w)))]
    except (RuntimeError, TypeError, ValueError):
        return None


def _torchcodec_make_decoder(VideoDecoder, path: str, one_device: str, transforms):
    kwargs: Dict[str, Any] = {"device": one_device}
    if transforms is not None:
        kwargs["transforms"] = transforms
    return VideoDecoder(path, **kwargs)


def _torchcodec_build_decoder(VideoDecoder, path: str, device: str, transforms, set_cuda_backend, allow_cpu_fallback: bool = True):
    decoder = None
    mode = "torchcodec-cpu"
    try:
        if str(device).lower().startswith("cuda") and callable(set_cuda_backend):
            try:
                with set_cuda_backend("beta"):
                    decoder = _torchcodec_make_decoder(VideoDecoder, path, device, transforms)
                return decoder, "torchcodec-gpu-beta"
            except Exception:
                decoder = _torchcodec_make_decoder(VideoDecoder, path, device, transforms)
                return decoder, "torchcodec-gpu"
        decoder = _torchcodec_make_decoder(VideoDecoder, path, device, transforms)
        mode = "torchcodec-gpu" if str(device).lower().startswith("cuda") else "torchcodec-cpu"
    except Exception:
        if str(device).lower().startswith("cuda"):
            mode = "torchcodec-gpu-open-failed"
            if bool(allow_cpu_fallback):
                try:
                    decoder = _torchcodec_make_decoder(VideoDecoder, path, "cpu", transforms)
                    mode = "torchcodec-cpu-fallback"
                except Exception:
                    decoder = None
        else:
            mode = "torchcodec-cpu-open-failed"
    return decoder, mode


def _torchcodec_metadata(decoder) -> Tuple[float, float]:
    fps = 0.0
    dur = 0.0
    try:
        md = getattr(decoder, "metadata", None)
        if md is None:
            return 30.0, 0.0
        fps = _first_float(
            [getattr(md, "average_fps", 0.0), getattr(md, "average_fps_from_header", 0.0), getattr(md, "fps", 0.0)],
            0.0,
        )
        dur = _first_float(
            [getattr(md, "duration_seconds", 0.0), getattr(md, "end_stream_seconds", 0.0), getattr(md, "duration", 0.0)],
            0.0,
        )
        if dur <= 0.0:
            n_frames = int(
                _first_float(
                    [getattr(md, "num_frames", 0.0), getattr(md, "num_frames_from_content", 0.0), getattr(md, "num_frames_from_header", 0.0)],
                    0.0,
                )
            )
            if n_frames > 0 and fps > 1e-6:
                dur = float(n_frames) / float(max(1e-6, fps))
    except (AttributeError, RuntimeError, TypeError, ValueError):
        pass
    return (30.0 if fps <= 1e-6 else float(fps)), float(max(0.0, dur))


def _open_torchcodec_video(
    path: str,
    prefer_gpu: bool = False,
    resize_dims: Optional[Tuple[int, int]] = None,
    allow_cpu_fallback: bool = True,
):
    imports = _torchcodec_imports()
    if imports is None:
        return None, 0.0, 0.0, "torchcodec-unavailable"
    if not path or not os.path.exists(path):
        return None, 0.0, 0.0, "no-path"
    torch, VideoDecoder, set_cuda_backend, resize_cls = imports
    device = _torchcodec_device(torch, prefer_gpu)
    transforms = _torchcodec_resize_transforms(resize_dims, resize_cls)
    decoder, mode = _torchcodec_build_decoder(
        VideoDecoder,
        path,
        device,
        transforms,
        set_cuda_backend,
        allow_cpu_fallback=bool(allow_cpu_fallback),
    )
    if decoder is None:
        return None, 0.0, 0.0, str(mode or "torchcodec-open-failed")
    fps, dur = _torchcodec_metadata(decoder)
    return decoder, fps, dur, mode


__all__ = ["_open_torchcodec_video"]
