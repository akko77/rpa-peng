"""Image template matcher using OpenCV.

Workflow:
    matcher = TemplateMatcher(templates_dir="templates/")
    result = matcher.match_group(template_group, region=(x,y,w,h))
    # result is MatchResult or None
"""
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

# Default multi-scale factors. 1.0 first so exact-match wins fast.
DEFAULT_SCALES: Sequence[float] = (1.0, 0.95, 1.05, 0.9, 1.1)


@dataclass
class MatchResult:
    found: bool
    score: float            # 0..1
    center: Tuple[int, int]  # absolute screen coordinates
    top_left: Tuple[int, int]
    width: int
    height: int
    variant_file: str
    scale: float

    def to_dict(self):
        return {
            "found": self.found,
            "score": self.score,
            "center": list(self.center),
            "top_left": list(self.top_left),
            "width": self.width,
            "height": self.height,
            "variant_file": self.variant_file,
            "scale": self.scale,
        }


class TemplateMatcher:
    """Matches TemplateGroup variants against screen captures.

    Lazily imports cv2, numpy, PIL so the rest of the app can be imported
    in environments where opencv isn't installed yet.
    """

    def __init__(self, templates_dir: Union[str, Path], scales: Sequence[float] = DEFAULT_SCALES):
        self.templates_dir = Path(templates_dir)
        self.scales = tuple(scales)

    # ---------- public ----------
    def match_group(
        self,
        group,                                      # TemplateGroup
        region: Optional[Tuple[int, int, int, int]] = None,
        confidence_override: Optional[float] = None,
    ) -> Optional[MatchResult]:
        """Match a TemplateGroup against the current screen.

        - region overrides group.default_region (if both None, full screen).
        - confidence_override overrides per-variant confidence.
        - Uses group.match_strategy (first_hit | best_score).
        Returns MatchResult on success, None on miss.
        """
        import cv2
        import numpy as np

        if not group.variants:
            return None

        eff_region = region if region is not None else group.default_region
        screenshot_bgr, origin = self._grab_screen_bgr(eff_region)

        strategy = group.match_strategy
        best: Optional[MatchResult] = None

        for variant in group.variants:
            tpl_bgr = self._load_template_bgr(group.name, variant.file)
            if tpl_bgr is None:
                continue
            conf_threshold = (
                confidence_override
                if confidence_override is not None
                else (variant.confidence or group.default_confidence)
            )
            result = self._match_one(
                screenshot_bgr, tpl_bgr, conf_threshold, origin, variant.file
            )
            if result is None:
                continue
            if strategy == "first_hit":
                return result
            if best is None or result.score > best.score:
                best = result

        return best

    # ---------- internals ----------
    def _grab_screen_bgr(self, region: Optional[Tuple[int, int, int, int]]):
        """Return (numpy BGR image, (origin_x, origin_y)) for absolute-coord conversion."""
        import numpy as np
        import cv2
        import pyautogui

        if region is not None:
            x, y, w, h = region
            img = pyautogui.screenshot(region=(x, y, w, h))
            origin = (x, y)
        else:
            img = pyautogui.screenshot()
            origin = (0, 0)
        arr = np.array(img)  # RGB
        bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
        return bgr, origin

    def _load_template_bgr(self, group_name: str, file_rel: str):
        import cv2
        path = self.templates_dir / group_name / file_rel
        if not path.exists():
            # Allow file to be an absolute path or relative to templates_dir/<group_name>
            alt = self.templates_dir / file_rel
            if not alt.exists():
                return None
            path = alt
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        return img

    def _match_one(
        self,
        screenshot_bgr,
        template_bgr,
        conf_threshold: float,
        origin: Tuple[int, int],
        variant_file: str,
    ) -> Optional[MatchResult]:
        import cv2
        import numpy as np

        best_score = -1.0
        best_loc = (0, 0)
        best_w = 0
        best_h = 0
        best_scale = 1.0

        ss_h, ss_w = screenshot_bgr.shape[:2]
        for s in self.scales:
            if s == 1.0:
                tpl = template_bgr
            else:
                new_w = max(1, int(round(template_bgr.shape[1] * s)))
                new_h = max(1, int(round(template_bgr.shape[0] * s)))
                tpl = cv2.resize(template_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
            th, tw = tpl.shape[:2]
            if th > ss_h or tw > ss_w:
                continue
            res = cv2.matchTemplate(screenshot_bgr, tpl, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
            if max_val > best_score:
                best_score = float(max_val)
                best_loc = max_loc
                best_w, best_h = tw, th
                best_scale = s

        if best_score < conf_threshold:
            return None

        abs_x = best_loc[0] + origin[0]
        abs_y = best_loc[1] + origin[1]
        center = (abs_x + best_w // 2, abs_y + best_h // 2)
        return MatchResult(
            found=True,
            score=best_score,
            center=center,
            top_left=(abs_x, abs_y),
            width=best_w,
            height=best_h,
            variant_file=variant_file,
            scale=best_scale,
        )
