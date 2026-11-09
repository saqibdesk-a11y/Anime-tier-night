"""Sharpens an enlarged picture by letting Z-Image-Turbo redraw its fine detail at low strength, so the
picture stays the same but the lines and textures are crisp at the bigger size. Offline tool.

Usage:  python art/refine.py <image in ComfyUI/input> <out.webp> "<what the picture shows>" [denoise]
"""
import io
import json
import sys
import time
import urllib.parse
import urllib.request

from PIL import Image

COMFY = "http://127.0.0.1:8188"


def call(path, data=None):
    req = urllib.request.Request(COMFY + path, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def main():
    name, out, prompt = sys.argv[1], sys.argv[2], sys.argv[3]
    denoise = float(sys.argv[4]) if len(sys.argv) > 4 else 0.3
    wf = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "z_image_turbo_bf16.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "lumina2"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "4": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 3.0}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "6": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}},
        "7": {"class_type": "LoadImage", "inputs": {"image": name}},
        "8": {"class_type": "VAEEncode", "inputs": {"pixels": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "KSampler", "inputs": {"model": ["4", 0], "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["8", 0],
                                                   "seed": 11, "steps": 9, "cfg": 1.0, "sampler_name": "res_multistep",
                                                   "scheduler": "simple", "denoise": denoise}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["3", 0]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "gamenight_refine"}},
    }
    pid = json.loads(call("/prompt", {"prompt": wf}))["prompt_id"]
    t = time.time()
    while True:
        hist = json.loads(call("/history/" + pid))
        if pid in hist:
            entry = hist[pid]
            if entry.get("status", {}).get("status_str") == "error":
                raise SystemExit(json.dumps(entry["status"])[:800])
            img = entry["outputs"]["11"]["images"][0]
            raw = call("/view?" + urllib.parse.urlencode({"filename": img["filename"], "subfolder": img["subfolder"], "type": img["type"]}))
            break
        time.sleep(2)
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im.save(out, "WEBP", quality=86, method=6)
    print(f"{out} {im.size} in {time.time() - t:.0f}s")


if __name__ == "__main__":
    main()
