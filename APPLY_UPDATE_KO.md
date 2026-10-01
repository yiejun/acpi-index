# 수정본 적용 방법

1. ZIP을 풀고 `acpi-index` 폴더 안의 파일들을 기존 프로젝트 폴더에 덮어쓰세요. 숨겨진 `.github` 폴더도 포함해야 합니다. 기존 `.git` 폴더와 `.env`는 그대로 유지하세요.
2. 기존 프로젝트 루트에서 아래 명령을 실행하세요.

```bash
pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m analysis.build_dashboard
python -m http.server 8000 --directory docs
```

3. 브라우저에서 `http://localhost:8000`을 열어 확인하세요.
4. 확인 후 아래 명령으로 기존 GitHub 저장소에 반영하세요.

```bash
git add README.md APPLY_UPDATE_KO.md package.json analysis scripts tests scrapers docs .github/workflows/scrape.yml data/processed/acpi_level.parquet data/processed/basket_daily.parquet
git commit -m "Fix ACPI price index and redesign dashboard"
git push origin main
```

5. GitHub Pages 설정은 기존처럼 `main` 브랜치의 `/docs`를 사용하세요. Actions에서 **Update ACPI quotes → Run workflow**를 한 번 실행하세요. 기존 API secrets를 다시 입력할 필요는 없습니다.

## 달라진 계산

- 메인 지수: GPU 70%, API 30% 고정 비중. 이 비중은 프로젝트에서 정한 값이며 시장 지출 비중의 추정치가 아닙니다.
- GPU 업체별 비중은 25%, API 모델별 비중은 1/3입니다. 업체 안의 구성·지역도 고정합니다.
- 13개 고정 가격 항목, 기준일 2026-06-05, 기준값 100.
- 첨부된 데이터의 고정 항목 가격은 해당 기간에 변하지 않아 재계산한 선은 100으로 평평합니다. 기존 급등·급락은 새 계산에서 사라졌습니다.
- `analysis/basket.json`을 지우지 마세요. 구성 항목과 기준일을 고정하는 파일입니다.
- 수집 누락은 최대 7일간 마지막 값 유지와 날짜 표시, 이후 지수 미계산 처리합니다.
- 전력·주가는 메인 지수에 섞지 않고 별도 참고 정보로 표시합니다.

`acpi-preview.html`은 전달 시점의 데이터가 포함된 독립 미리보기입니다. 더블클릭하면 서버 없이 열립니다. 실제 배포 파일은 ZIP의 `docs` 폴더입니다.

계산 회귀 테스트 9개와 DOM 기능 검증을 통과했습니다. 새 코드로 외부 가격을 실제 재수집하는 것과 GitHub 배포는 이 수정본을 반영한 뒤 Actions에서 확인해야 합니다. 로컬 미리보기 URL에 대한 브라우저 접근 제한 때문에 이번 작업에서는 실제 브라우저의 시각적 검증을 완료하지 못했습니다.
