"""SAM 3.1 text-prompt detection with the masks of ComfyUI's SAM3_Detect, in a fraction of its graphics memory (Artegra
Enhancer 5.0.2; Max, 20 Nov 2026: "Fold into 5.0.2").

ComfyUI's SAM3_Detect (comfy_extras/nodes_sam3.py, ComfyUI 0.42.4) asks the detector for every query mask upsampled to the
whole input on the card (comfy/ldm/sam3/detector.py, SAM3Detector.forward with orig_size: F.interpolate of the
[1, 200, h, w] masks to the input size), about 400 bytes per input pixel in fp16 (24.7 GiB at 66 MP), and then keeps the
top-scoring ones. This node asks the detector for its masks at its own resolution (orig_size=None), applies SAM3_Detect's
own selection on the scores (sigmoid, > threshold, the top max_detections), scales the kept boxes by [W, H, W, H] in the
model dtype on the card as the detector does, and upsamples ONLY the kept masks, each with the same F.interpolate call on
its own channel of the same tensor. Bilinear interpolation computes every channel alone from the same weights, so each kept
mask is the stock node's; the refine (SAM3_Detect's own _refine_mask), the union and the outputs are the stock code's.
Graphics memory: the low-resolution masks plus about 13 bytes per input pixel for the one kept mask being refined.

Text prompts only, as the product's graphs send (no boxes or points). engine/graph_v5t.py uses it for a stage whose padded
input is above engine/planner.SAM_STOCK_MAX_MP; every smaller stage keeps SAM3_Detect itself.
tests/worker/test_sam_lean.py runs it against SAM3_Detect's own code on synthetic images: 0 differing mask values."""
import torch
import torch.nn.functional as F


class ClaudeSAM3DetectLean:
    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"model": ("MODEL",), "image": ("IMAGE",), "conditioning": ("CONDITIONING",),
                             "threshold": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
                             "refine_iterations": ("INT", {"default": 2, "min": 0, "max": 5}),
                             "individual_masks": ("BOOLEAN", {"default": False})}}
    RETURN_TYPES = ("MASK", "BOUNDING_BOX")
    RETURN_NAMES = ("masks", "bboxes")
    FUNCTION = "run"
    CATEGORY = "claude_creative"

    def run(self, model, image, conditioning, threshold=0.5, refine_iterations=2, individual_masks=False):
        import comfy.model_management
        import comfy.utils
        from comfy_extras.nodes_sam3 import _extract_text_prompts, _refine_mask
        B, H, W, C = image.shape
        image_in = comfy.utils.common_upscale(image[..., :3].movedim(-1, 1), 1008, 1008, "bilinear", crop="disabled")
        comfy.model_management.load_model_gpu(model)
        device = comfy.model_management.get_torch_device()
        dtype = model.model.get_dtype()
        sam3_model = model.model.diffusion_model
        cond_list = _extract_text_prompts(conditioning, device, dtype) if conditioning is not None and len(conditioning) > 0 else []
        all_bbox_dicts = []
        all_masks = []
        pbar = comfy.utils.ProgressBar(B)
        for b in range(B):
            frame = image_in[b:b + 1].to(device=device, dtype=dtype)
            frame_bbox_dicts = []
            frame_masks = []
            for text_embeddings, text_mask, max_det in cond_list:
                results = sam3_model(frame, text_embeddings=text_embeddings, text_mask=text_mask, boxes=None,
                                     threshold=threshold, orig_size=None)
                boxes = results["boxes"]
                boxes = boxes * torch.tensor([W, H, W, H], device=boxes.device, dtype=boxes.dtype)   # detector.py, orig_size
                pred_boxes = boxes[0]
                scores = results["scores"][0]
                masks_lo = results["masks"]                       # [1, queries, h, w], the detector's own resolution

                probs = scores.sigmoid()
                keep = probs > threshold
                kept_boxes = pred_boxes[keep].cpu()
                kept_scores = probs[keep].cpu()
                kept_index = keep.nonzero().flatten().cpu()        # the queries masks[keep] would hold, in that order

                order = kept_scores.argsort(descending=True)[:max_det]
                kept_boxes = kept_boxes[order]
                kept_scores = kept_scores[order]
                kept_index = kept_index[order]

                for box, score in zip(kept_boxes, kept_scores):
                    frame_bbox_dicts.append({
                        "x": float(box[0]), "y": float(box[1]),
                        "width": float(box[2] - box[0]), "height": float(box[3] - box[1]),
                        "score": float(score),
                    })
                for q, box in zip(kept_index.tolist(), kept_boxes):
                    m = F.interpolate(masks_lo[:, q:q + 1], size=(H, W), mode="bilinear", align_corners=False)[0, 0]
                    frame_masks.append(_refine_mask(sam3_model, image[b], m, box, H, W, device, dtype, refine_iterations))
                    del m
                del results, masks_lo

            all_bbox_dicts.append(frame_bbox_dicts)
            if len(frame_masks) > 0:
                combined = torch.cat(frame_masks, dim=0)
                if individual_masks:
                    all_masks.append(combined)
                else:
                    all_masks.append((combined > 0).any(dim=0).float())
            else:
                if individual_masks:
                    all_masks.append(torch.zeros(0, H, W, device=comfy.model_management.intermediate_device()))
                else:
                    all_masks.append(torch.zeros(H, W, device=comfy.model_management.intermediate_device()))
            pbar.update(1)

        idev = comfy.model_management.intermediate_device()
        all_masks = [m.to(idev) for m in all_masks]
        mask_out = torch.cat(all_masks, dim=0) if individual_masks else torch.stack(all_masks)
        return (mask_out, all_bbox_dicts)
