"""
World Happiness Report - Southeast Asia analysis.

Filters World Happiness Report (WHR) data down to the 11 Southeast Asian
countries and produces summary tables and charts:

  * latest-year happiness ranking within the region
  * regional averages vs. the rest of the world
  * how each factor (GDP, social support, health, ...) relates to happiness
  * happiness trend per country over time (when the data has several years)

Works with the common WHR data layouts:

  * the WHR panel file ("DataForTable2.1.xls" / Kaggle "world-happiness-report.csv")
    with columns like "Country name", "year", "Life Ladder", ...
  * single-year files (Kaggle "world-happiness-report-2021.csv", "2019.csv", ...)
    with columns like "Country name", "Ladder score" or "Score". Pass several of
    them and the year is read from each file name.

Usage:
    pip install pandas matplotlib openpyxl xlrd
    python sea_happiness_analysis.py DataForTable2.1.xls
    python sea_happiness_analysis.py 2015.csv 2016.csv 2017.csv 2018.csv 2019.csv
    python sea_happiness_analysis.py data.csv --out results/
"""

import argparse
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import MaxNLocator

# --- Region definition -------------------------------------------------------

# Canonical name -> spellings used across WHR editions / other datasets.
SEA_COUNTRIES = {
	"Brunei": ["brunei", "brunei darussalam"],
	"Cambodia": ["cambodia"],
	"Indonesia": ["indonesia"],
	"Laos": ["laos", "lao pdr", "lao people's democratic republic"],
	"Malaysia": ["malaysia"],
	"Myanmar": ["myanmar", "burma"],
	"Philippines": ["philippines", "the philippines"],
	"Singapore": ["singapore"],
	"Thailand": ["thailand"],
	"Timor-Leste": ["timor-leste", "east timor", "timor leste"],
	"Vietnam": ["vietnam", "viet nam"],
}
ALIAS_TO_COUNTRY = {
	alias: name for name, aliases in SEA_COUNTRIES.items() for alias in aliases
}

# --- Column normalisation ----------------------------------------------------

# Standard column -> names it appears under in different WHR files.
COLUMN_ALIASES = {
	"country": ["country name", "country", "country or region"],
	"region": ["regional indicator", "region"],
	"year": ["year"],
	"score": [
		"life ladder", "ladder score", "life evaluation", "happiness score",
		"score",
	],
	"gdp": [
		"log gdp per capita", "logged gdp per capita",
		"economy (gdp per capita)", "gdp per capita",
	],
	"social_support": ["social support", "family"],
	"life_expectancy": [
		"healthy life expectancy at birth", "healthy life expectancy",
		"health (life expectancy)",
	],
	"freedom": ["freedom to make life choices", "freedom"],
	"generosity": ["generosity"],
	"corruption": [
		"perceptions of corruption", "trust (government corruption)",
	],
}

FACTORS = [
	"gdp", "social_support", "life_expectancy", "freedom", "generosity",
	"corruption",
]
FACTOR_LABELS = {
	"gdp": "GDP per capita",
	"social_support": "Social support",
	"life_expectancy": "Healthy life expectancy",
	"freedom": "Freedom of choice",
	"generosity": "Generosity",
	"corruption": "Perceived corruption",
}

# Chart colours: one hue for magnitude, a two-pole pair for +/- correlation.
BLUE = "#2a78d6"
ORANGE = "#eb6834"
GRAY = "#b5b3ad"
TEXT = "#0b0b0b"
TEXT_MUTED = "#52514e"


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
	lookup = {c.strip().lower(): c for c in df.columns}
	rename = {}
	for std, aliases in COLUMN_ALIASES.items():
		for alias in aliases:
			if alias in lookup:
				rename[lookup[alias]] = std
				break
	df = df.rename(columns=rename)
	keep = [c for c in COLUMN_ALIASES if c in df.columns]
	return df[keep]


def load_file(path: Path) -> pd.DataFrame:
	if path.suffix.lower() in (".xls", ".xlsx"):
		df = pd.read_excel(path)
	else:
		df = pd.read_csv(path)
	df = normalise_columns(df)
	missing = {"country", "score"} - set(df.columns)
	if missing:
		sys.exit(f"{path}: could not find column(s) {sorted(missing)}")
	if "year" not in df.columns:
		match = re.search(r"(19|20)\d{2}", path.stem)
		if not match:
			sys.exit(f"{path}: no 'year' column and no year in the file name")
		df["year"] = int(match.group(0))
	return df


def load_data(paths: list[Path]) -> pd.DataFrame:
	df = pd.concat([load_file(p) for p in paths], ignore_index=True)
	df["year"] = df["year"].astype(int)
	df["country"] = df["country"].astype(str).str.strip()
	canonical = df["country"].str.lower().map(ALIAS_TO_COUNTRY)
	df["is_sea"] = canonical.notna()
	df.loc[df["is_sea"], "country"] = canonical[df["is_sea"]]
	return df


# --- Analysis ----------------------------------------------------------------

def latest_ranking(sea: pd.DataFrame, world: pd.DataFrame) -> pd.DataFrame:
	year = sea["year"].max()
	world_year = world[world["year"] == year].copy()
	world_year["world_rank"] = world_year["score"].rank(
		ascending=False, method="min").astype(int)
	ranked = world_year[world_year["is_sea"]].sort_values(
		"score", ascending=False)
	ranked.insert(0, "sea_rank", range(1, len(ranked) + 1))
	cols = ["sea_rank", "world_rank", "country", "score"] + [
		f for f in FACTORS if f in ranked.columns]
	return ranked[cols].reset_index(drop=True)


def region_vs_world(sea: pd.DataFrame, world: pd.DataFrame) -> pd.DataFrame:
	year = sea["year"].max()
	cols = ["score"] + [f for f in FACTORS if f in world.columns]
	latest = world[world["year"] == year]
	return pd.DataFrame({
		"Southeast Asia (mean)": latest[latest["is_sea"]][cols].mean(),
		"Rest of world (mean)": latest[~latest["is_sea"]][cols].mean(),
	}).round(3)


def factor_correlations(sea: pd.DataFrame) -> pd.Series:
	factors = [f for f in FACTORS if f in sea.columns]
	return (sea[factors + ["score"]].corr()["score"]
		.drop("score").sort_values(ascending=False).round(3))


def score_change(sea: pd.DataFrame) -> pd.DataFrame:
	first = sea.sort_values("year").groupby("country").first()
	last = sea.sort_values("year").groupby("country").last()
	out = pd.DataFrame({
		"first_year": first["year"], "first_score": first["score"],
		"last_year": last["year"], "last_score": last["score"],
	})
	out["change"] = out["last_score"] - out["first_score"]
	return out.sort_values("change", ascending=False).round(3)


# --- Charts ------------------------------------------------------------------

def style_axes(ax):
	for side in ("top", "right"):
		ax.spines[side].set_visible(False)
	for side in ("left", "bottom"):
		ax.spines[side].set_color(GRAY)
	ax.tick_params(colors=TEXT_MUTED, labelsize=9)
	ax.title.set_color(TEXT)


def plot_ranking(ranking: pd.DataFrame, year: int, out: Path):
	data = ranking.sort_values("score")
	fig, ax = plt.subplots(figsize=(8, 5))
	bars = ax.barh(data["country"], data["score"], color=BLUE, height=0.6)
	ax.bar_label(bars, fmt="%.2f", padding=4, color=TEXT_MUTED, fontsize=9)
	ax.set_xlabel("Happiness score (0-10)", color=TEXT_MUTED)
	ax.set_title(f"Southeast Asia happiness ranking, {year}", loc="left")
	ax.set_xlim(0, max(10, data["score"].max() + 0.8))
	ax.grid(axis="x", color=GRAY, alpha=0.3)
	ax.set_axisbelow(True)
	style_axes(ax)
	fig.tight_layout()
	fig.savefig(out / "01_ranking.png", dpi=150)
	plt.close(fig)


def plot_factor_heatmap(ranking: pd.DataFrame, year: int, out: Path):
	factors = [f for f in FACTORS if f in ranking.columns]
	if not factors:
		return
	data = ranking.set_index("country")[factors]
	# Scale each factor 0-1 within the region so columns are comparable.
	scaled = (data - data.min()) / (data.max() - data.min())
	fig, ax = plt.subplots(figsize=(9, 5.5))
	im = ax.imshow(scaled.values, cmap="Blues", aspect="auto", vmin=0, vmax=1)
	ax.set_xticks(range(len(factors)))
	ax.set_xticklabels([FACTOR_LABELS[f] for f in factors], rotation=30,
		ha="right")
	ax.set_yticks(range(len(data)))
	ax.set_yticklabels(data.index)
	for i in range(data.shape[0]):
		for j in range(data.shape[1]):
			value = data.iat[i, j]
			if pd.notna(value):
				dark = scaled.iat[i, j] > 0.6
				ax.text(j, i, f"{value:.2f}", ha="center", va="center",
					fontsize=8, color="white" if dark else TEXT)
	cbar = fig.colorbar(im, ax=ax, fraction=0.03)
	cbar.set_label("Relative to region (0 = lowest, 1 = highest)",
		color=TEXT_MUTED)
	ax.set_title(f"Happiness factors by country, {year} "
		"(rows ordered by score)", loc="left")
	style_axes(ax)
	fig.tight_layout()
	fig.savefig(out / "02_factor_heatmap.png", dpi=150)
	plt.close(fig)


def plot_correlations(corr: pd.Series, out: Path):
	data = corr.sort_values()
	colors = [BLUE if v >= 0 else ORANGE for v in data]
	fig, ax = plt.subplots(figsize=(7, 4))
	bars = ax.barh([FACTOR_LABELS[f] for f in data.index], data.values,
		color=colors, height=0.6)
	ax.bar_label(bars, fmt="%+.2f", padding=4, color=TEXT_MUTED, fontsize=9)
	ax.axvline(0, color=GRAY, linewidth=1)
	ax.set_xlim(-1.15, 1.15)
	ax.set_xlabel("Correlation with happiness score (all SEA rows)",
		color=TEXT_MUTED)
	ax.set_title("What moves happiness in Southeast Asia?", loc="left")
	style_axes(ax)
	fig.tight_layout()
	fig.savefig(out / "03_factor_correlations.png", dpi=150)
	plt.close(fig)


def plot_gdp_scatter(sea: pd.DataFrame, year: int, out: Path):
	if "gdp" not in sea.columns:
		return
	latest = sea[sea["year"] == year].dropna(subset=["gdp", "score"])
	fig, ax = plt.subplots(figsize=(7.5, 5))
	ax.scatter(latest["gdp"], latest["score"], s=60, color=BLUE,
		edgecolor="white", linewidth=1.5, zorder=3)
	for _, row in latest.iterrows():
		ax.annotate(row["country"], (row["gdp"], row["score"]),
			xytext=(6, 4), textcoords="offset points", fontsize=9,
			color=TEXT_MUTED)
	ax.set_xlabel("GDP per capita (as reported in the source data)",
		color=TEXT_MUTED)
	ax.set_ylabel("Happiness score", color=TEXT_MUTED)
	ax.set_title(f"Wealth vs. happiness, {year}", loc="left")
	ax.grid(color=GRAY, alpha=0.3)
	style_axes(ax)
	fig.tight_layout()
	fig.savefig(out / "04_gdp_vs_happiness.png", dpi=150)
	plt.close(fig)


def plot_trends(sea: pd.DataFrame, out: Path):
	if sea["year"].nunique() < 2:
		return
	# Small multiples: each country in blue against the regional mean in gray.
	regional = sea.groupby("year")["score"].mean()
	countries = sorted(sea["country"].unique())
	ncols = 4
	nrows = -(-len(countries) // ncols)
	fig, axes = plt.subplots(nrows, ncols, figsize=(12, 2.6 * nrows),
		sharex=True, sharey=True)
	axes = axes.flatten()
	for ax, country in zip(axes, countries):
		series = sea[sea["country"] == country].sort_values("year")
		ax.plot(regional.index, regional.values, color=GRAY, linewidth=2,
			label="SEA mean")
		ax.plot(series["year"], series["score"], color=BLUE, linewidth=2,
			marker="o", markersize=3, label=country)
		ax.set_title(country, loc="left", fontsize=10)
		ax.xaxis.set_major_locator(MaxNLocator(nbins=4, integer=True))
		ax.tick_params(labelbottom=True)
		ax.grid(color=GRAY, alpha=0.25)
		style_axes(ax)
	for ax in axes[len(countries):]:
		ax.set_visible(False)
	handles = [
		plt.Line2D([], [], color=BLUE, linewidth=2, label="Country"),
		plt.Line2D([], [], color=GRAY, linewidth=2, label="SEA mean"),
	]
	fig.legend(handles=handles, loc="upper right", frameon=False)
	fig.suptitle("Happiness score over time", x=0.01, ha="left",
		color=TEXT)
	fig.tight_layout(rect=(0, 0, 1, 0.96))
	fig.savefig(out / "05_trends.png", dpi=150)
	plt.close(fig)


# --- Main --------------------------------------------------------------------

def main():
	parser = argparse.ArgumentParser(description=__doc__,
		formatter_class=argparse.RawDescriptionHelpFormatter)
	parser.add_argument("files", nargs="+", type=Path,
		help="WHR data file(s): .csv, .xls or .xlsx")
	parser.add_argument("--out", type=Path, default=Path("sea_output"),
		help="output folder for tables and charts (default: sea_output)")
	args = parser.parse_args()
	args.out.mkdir(parents=True, exist_ok=True)

	world = load_data(args.files)
	sea = world[world["is_sea"]].copy()
	if sea.empty:
		sys.exit("No Southeast Asian countries found in the data.")

	missing = sorted(set(SEA_COUNTRIES) - set(sea["country"]))
	latest_year = int(sea["year"].max())
	pd.set_option("display.width", 140)

	print(f"Southeast Asia rows: {len(sea)} "
		f"({sea['year'].min()}-{latest_year}, "
		f"{sea['country'].nunique()} countries)")
	if missing:
		print(f"Not in the data: {', '.join(missing)}")

	ranking = latest_ranking(sea, world)
	no_latest = sorted(set(sea["country"]) - set(ranking["country"]))
	if no_latest:
		print(f"No {latest_year} data for: {', '.join(no_latest)} "
			"(left out of the ranking, heatmap and scatter)")
	print(f"\n== Ranking, {latest_year} ==")
	print(ranking.round(3).to_string(index=False))

	comparison = region_vs_world(sea, world)
	print(f"\n== Southeast Asia vs rest of world, {latest_year} ==")
	print(comparison.to_string())

	corr = factor_correlations(sea)
	print("\n== Correlation of each factor with happiness (SEA) ==")
	print(corr.rename(index=FACTOR_LABELS).to_string())

	sea.drop(columns="is_sea").sort_values(["country", "year"]).to_csv(
		args.out / "sea_data.csv", index=False)
	ranking.to_csv(args.out / "ranking_latest.csv", index=False)
	comparison.to_csv(args.out / "sea_vs_world.csv")
	corr.to_csv(args.out / "factor_correlations.csv")

	if sea["year"].nunique() > 1:
		change = score_change(sea)
		print("\n== Change in happiness score, first to last year ==")
		print(change.to_string())
		change.to_csv(args.out / "score_change.csv")

	plot_ranking(ranking, latest_year, args.out)
	plot_factor_heatmap(ranking, latest_year, args.out)
	plot_correlations(corr, args.out)
	plot_gdp_scatter(sea, latest_year, args.out)
	plot_trends(sea, args.out)
	print(f"\nTables and charts written to {args.out.resolve()}")


if __name__ == "__main__":
	main()
