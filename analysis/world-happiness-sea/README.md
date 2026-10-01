# World Happiness: Southeast Asia

`sea_happiness_analysis.py` filters World Happiness Report data down to the 11
Southeast Asian countries (Brunei, Cambodia, Indonesia, Laos, Malaysia, Myanmar,
Philippines, Singapore, Thailand, Timor-Leste, Vietnam) and analyses them.

## Data

Use either of these:

- **WHR panel data** (all years): `DataForTable2.1.xls` from
  <https://worldhappiness.report/data/>, or Kaggle's `world-happiness-report.csv`.
- **Single-year files**: Kaggle's `world-happiness-report-2021.csv`, or
  `2015.csv` ... `2019.csv`. Pass several and the year comes from each file name.

Country spellings such as "Viet Nam" or "Lao PDR" are matched automatically.

## Run

```bash
pip install pandas matplotlib openpyxl xlrd
python sea_happiness_analysis.py DataForTable2.1.xls --out sea_output
```

## Output

Printed to the console and saved in `--out`:

| File | Contents |
|---|---|
| `sea_data.csv` | Southeast Asia rows only |
| `ranking_latest.csv` | latest-year ranking, regional and world rank |
| `sea_vs_world.csv` | regional mean vs rest-of-world mean per factor |
| `factor_correlations.csv` | correlation of each factor with the happiness score |
| `score_change.csv` | first-to-last-year change per country (multi-year data) |
| `01_ranking.png` | ranking bar chart |
| `02_factor_heatmap.png` | factor values per country |
| `03_factor_correlations.png` | factor correlations |
| `04_gdp_vs_happiness.png` | GDP vs happiness scatter |
| `05_trends.png` | per-country trend vs regional mean (multi-year data) |

## Quarto report

`sea_happiness_analysis.qmd` runs the same analysis as a Quarto document. Set
`DATA_FILES` in its first code cell (or pass it as a parameter), then:

```bash
pip install jupyter pandas matplotlib openpyxl xlrd
quarto render sea_happiness_analysis.qmd
# or, without editing the file (needs `pip install papermill`):
quarto render sea_happiness_analysis.qmd -P DATA_FILES:"['DataForTable2.1.xls']"
```
