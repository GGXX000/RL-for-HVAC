# 论文中报告的 SWT 规则

1. 若 SAT < 13 C 且 VAVBoxcore_damper > 0.68，则 SWT = 11.0 C
2. 若 SAT < 13 C 且 VAVBoxcore_damper <= 0.68 且 Tout_2h < 19.0 C，则 SWT = 11.5 C
3. 若 SAT < 13 C 且 VAVBoxcore_damper <= 0.68 且 Tout_2h >= 19.0 C 且 Tout_4h > 23.0 C，则 SWT = 12.5 C
4. 若 SAT < 13 C 且 VAVBoxcore_damper <= 0.68 且 Tout_2h >= 19.0 C 且 Tout_4h <= 23.0 C，则 SWT = 11.0 C
5. 若 SAT >= 13 C 且 ZATeast > 24.0 C，则 SWT = 12.0 C
6. 若 SAT >= 13 C 且 ZATeast <= 24.0 C 且 SAT < 14.5 C，则 SWT = 13.0 C
7. 若 SAT >= 13 C 且 ZATeast <= 24.0 C 且 SAT >= 14.5 C，则 SWT = 14.0 C
