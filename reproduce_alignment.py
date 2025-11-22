
from typing import Dict, List, Any
from dataclasses import dataclass

@dataclass
class PathMock:
    name: str

@dataclass
class PlanMock:
    path: PathMock
    trim_start: int = 0
    source_num_frames: int = 1000
    alignment_frames: int = 0
    alignment_status: str = ""

def run_alignment_logic():
    # Setup
    ref_plan = PlanMock(PathMock("CtrlHD.mkv"))
    tgt_plan = PlanMock(PathMock("Kira.mkv"))
    plans = [ref_plan, tgt_plan]
    
    # Simulate measurements: Kira is -361 relative to CtrlHD
    # applied_frames comes from update_offsets_file
    # It should contain the measured offsets.
    # If Kira is -361, applied_frames should have {'Kira.mkv': -361}
    applied_frames = {"Kira.mkv": -361}
    
    # Logic from alignment_runner.py
    final_map: Dict[str, int] = {ref_plan.path.name: 0}
    for name, frames in applied_frames.items():
        final_map[name] = frames
    
    print(f"Final Map: {final_map}")

    baseline = min(final_map.values()) if final_map else 0
    print(f"Baseline: {baseline}")
    
    baseline_shift = int(-baseline) if baseline < 0 else 0
    print(f"Baseline Shift: {baseline_shift}")

    final_adjustments: Dict[str, int] = {}
    for plan in plans:
        desired = final_map.get(plan.path.name)
        if desired is None:
            continue
        adjustment = int(desired - baseline)
        print(f"Plan {plan.path.name}: Desired {desired}, Adjustment {adjustment}")
        
        if adjustment:
            plan.trim_start = plan.trim_start + adjustment
            plan.source_num_frames = None
            plan.alignment_frames = adjustment
            plan.alignment_status = "auto"
        else:
            plan.alignment_frames = 0
            plan.alignment_status = "auto"
        final_adjustments[plan.path.name] = adjustment

    print(f"Result: CtrlHD trim={ref_plan.trim_start}, Kira trim={tgt_plan.trim_start}")

if __name__ == "__main__":
    run_alignment_logic()
