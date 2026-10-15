# Factory CCTV test clips

The three active factory clips are unchanged examples from the [Video Dataset for Safe and Unsafe Behaviours](https://data.mendeley.com/datasets/xjmtb22pff/1), by Oğuzhan Önal and Emre Dandıl (Mendeley Data V1, 2024, DOI [10.17632/xjmtb22pff.1](https://doi.org/10.17632/xjmtb22pff.1)). The dataset is licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). File-level credits are listed in `prahari-dashboard/public/videos/ATTRIBUTIONS.md`.

| Dashboard file | Dataset class | Duration |
| --- | --- | ---: |
| `cctv-0_te1.mp4` | Safe Walkway Violation | 15 s |
| `cctv-1_te1.mp4` | Unauthorized Intervention | 17 s |
| `cctv-3_te1.mp4` | Carrying Overload with Forklift | 10 s |

The clips are 1920×1080 fixed-camera views. Their source dataset has video-level behavior labels, not object bounding boxes, so these clips support visual and inference checks but do not provide object-detection training labels or an overall accuracy score.
