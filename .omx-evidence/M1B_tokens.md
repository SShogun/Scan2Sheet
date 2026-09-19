# M1B Token / Execution Evidence

Part: Milestone 1 — Part 1B Adaptive Preprocessing V1  
Branch: `milestone-1b-preprocessing`  
Date: 2026-09-19 (Asia/Kolkata)

| Metric | Start | End |
|---|---:|---:|
| root tokens | unavailable | unavailable |
| subagent tokens | unavailable | unavailable |
| cached input | unavailable | unavailable |
| output tokens | unavailable | unavailable |
| number of agents | 3 bounded logical roles | 3 bounded logical roles + Sourcery external review |
| number of turns | unavailable | unavailable |
| wall-clock duration | unavailable | unavailable |
| files changed | 0 for Part 1B at start | imaging package + OCR integration + tests + CI + evidence/benchmark |
| tests added | 0 | 11 imaging/benchmark-specific tests (plus inherited M1A regression contracts) |
| tests passed | inherited M1A RED state | 21/21 after Sourcery fixes |

## External review evidence

Sourcery identified four blocking issues on PR #1:
- historical baseline overwrite risk;
- missing 180° orientation correction;
- missing OSD timeout;
- unbounded large-image analysis.

All four were fixed and regression-tested before final milestone sign-off.

Unavailable runtime token/turn metrics are intentionally not estimated.
