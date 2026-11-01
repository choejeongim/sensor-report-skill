# sensor-report

센서 CSV(CO2·온도·습도·기압 등)를 주면 한국어 한 페이지 리포트를 만들어 주는 Claude Code 스킬입니다.
아기 수면방(13개월) 프로필을 쓰면 취침·낮잠 시간대별로 환경이 기준에 맞았는지 평가합니다.

## 구성
- `SKILL.md` : Claude에게 주는 설명서(리포트 형식, 해석 규칙)
- `scripts/analyze.py` : 통계를 계산하는 프로그램 (Python 3, 추가 설치 없음)
- `profiles/baby_13m.json` : 아기 수면방 기준과 하루 일과 (숫자만 바꿔 쓸 수 있음)
- `example_report.md` : 결과 예시

## 사용
```
python3 scripts/analyze.py data.csv
python3 scripts/analyze.py data.csv --profile profiles/baby_13m.json
```
Claude Code에서는 `sensor-report` 폴더를 `~/.claude/skills/` 아래에 넣고 "이 data.csv로 공기 리포트 만들어 줘"라고 말하면 됩니다.

## CSV 형식 (예)
`time,device,temp_env,hum_env,pressure,gas_kohm,co2,temp_co2,hum_co2`

참고 기준은 의학적 진단이 아닙니다.
