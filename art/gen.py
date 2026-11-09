"""Makes the site's art with a local ComfyUI running Z-Image-Turbo. Offline tool: the site never runs it.

Usage:  python art/gen.py art/prompts/characters.json [--only id1,id2] [--seed N] [--resume]
        --resume skips images that already exist, so a stopped run picks up where it left off.
Each job in the JSON: {"id": "...", "out": "img/chars/x.webp", "w": 768, "h": 1024, "prompt": "...", "size": [384, 512]}
A shared "style" string from the file is added to every prompt. Results are saved as WebP next to the pages.
"""
import io
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request

from PIL import Image

COMFY = "http://127.0.0.1:8188"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the site folder


def call(path, data=None):
    req = urllib.request.Request(COMFY + path, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def workflow(prompt, w, h, seed):
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "z_image_turbo_bf16.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "lumina2"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "4": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 3.0}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": prompt}},
        "6": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["5", 0]}},
        "7": {"class_type": "EmptySD3LatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["4", 0], "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["7", 0],
                                                   "seed": seed, "steps": 9, "cfg": 1.0, "sampler_name": "res_multistep",
                                                   "scheduler": "simple", "denoise": 1.0}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": "gamenight"}},
    }


def run(job, style, seed):
    text = (job["prompt"] + " " + style).strip()
    pid = json.loads(call("/prompt", {"prompt": workflow(text, job.get("w", 768), job.get("h", 1024), seed)}))["prompt_id"]
    while True:
        hist = json.loads(call("/history/" + pid))
        if pid in hist:
            entry = hist[pid]
            if entry.get("status", {}).get("status_str") == "error":
                raise RuntimeError(json.dumps(entry["status"])[:500])
            img = entry["outputs"]["10"]["images"][0]
            raw = call("/view?" + urllib.parse.urlencode({"filename": img["filename"], "subfolder": img["subfolder"], "type": img["type"]}))
            break
        time.sleep(1)
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    if job.get("size"):
        im = im.resize(tuple(job["size"]), Image.LANCZOS)
    out = os.path.join(HERE, job["out"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    im.save(out, "WEBP", quality=job.get("q", 82), method=6)
    return out


def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8"))
    only = set(sys.argv[sys.argv.index("--only") + 1].split(",")) if "--only" in sys.argv else None
    base = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else None
    for job in spec["jobs"]:
        if only and job["id"] not in only:
            continue
        if "--resume" in sys.argv and os.path.isfile(os.path.join(HERE, job["out"])):
            continue  # already made (e.g. before a power cut)
        seed = job.get("seed", base if base is not None else random.randrange(2**31))
        t = time.time()
        out = run(job, spec.get("style", ""), seed)
        print(f"{job['id']}  seed={seed}  {time.time() - t:.1f}s  {os.path.getsize(out) // 1024}KB  {job['out']}", flush=True)


if __name__ == "__main__":
    main()
