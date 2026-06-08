---
name: "stock_analyzer"
description: "Analyze stocks and the market. Invoke this when the user wants to analyze a single stock, multiple stocks, or perform a market review."
---

# Stock Analyzer

This skill is based on the logic in `src/services/analyzer_service.py` and provides functionality to analyze stocks and the overall market.

## Output Structure (`AnalysisResult`)

The analysis function returns an `AnalysisResult` object (or a list of them), which has a rich structure. Below is a brief overview of its key components, along with a real output example:

The `dashboard` property contains the core analysis, divided into four main sections:
1.  **`core_conclusion`**: One-sentence summary, signal type, and position advice.
2.  **`data_perspective`**: Technical data, including trend status, price location, volume analysis, and chip structure.
3.  **`intelligence`**: Qualitative information, such as news, risk alerts, and positive catalysts.
4.  **`battle_plan`**: Actionable strategies, including sniper points (buy/sell targets), position strategies, and risk control checklists.

## Configuration (`Config`)

All analysis functions can accept an optional `config` object. This object contains all application configurations, such as API keys, notification settings, and analysis parameters.

If no `config` object is provided, the function will automatically use the global singleton instance loaded from the `.env` file.

**Reference:** [`Config`](src/config.py)

## Functions

### 1. Analyze a Single Stock

**Description:** Analyze a single stock and return the analysis results.

**When to use:** When the user asks to analyze a specific stock.

**Inputs:**
- `stock_code` (str): The stock code to analyze.
- `config` (Config, optional): Configuration object. Defaults to `None`.
- `full_report` (bool, optional): Whether to generate a full report. Defaults to `False`.
- `notifier` (NotificationService, optional): Notification service object. Defaults to `None`.

**Outputs:** `Optional[AnalysisResult]`
An `AnalysisResult` object containing the analysis results, or `None` if the analysis fails.

**Example:**

```python
from src.services.analyzer_service import analyze_stock

# Analyze a single stock
result = analyze_stock("600989")
if result:
    print(f"Stock: {result.name} ({result.code})")
    print(f"Sentiment Score: {result.sentiment_score}")
    print(f"Operation Advice: {result.operation_advice}")
```

**Reference:** [`analyze_stock`](src/services/analyzer_service.py)

### 2. Analyze Multiple Stocks

**Description:** Analyze a list of stock codes and return a list of analysis results.

**When to use:** When the user wants to analyze multiple stocks at once.

**Inputs:**
- `stock_codes` (List[str]): List of stock codes to analyze.
- `config` (Config, optional): Configuration object. Defaults to `None`.
- `full_report` (bool, optional): Whether to generate a full report for each stock. Defaults to `False`.
- `notifier` (NotificationService, optional): Notification service object. Defaults to `None`.

**Outputs:** `List[AnalysisResult]`
A list of `AnalysisResult` objects.

**Example:**

```python
from src.services.analyzer_service import analyze_stocks

# Analyze multiple stocks
results = analyze_stocks(["600989", "000001"])
for result in results:
    print(f"Stock: {result.name}, Operation Advice: {result.operation_advice}")
```

**Reference:** [`analyze_stocks`](src/services/analyzer_service.py)


### 3. Perform Market Review

**Description:** Perform a market review of the overall market and return a report.

**When to use:** When the user asks for a market overview, summary, or review.

**Inputs:**
- `config` (Config, optional): Configuration object. Defaults to `None`.
- `notifier` (NotificationService, optional): Notification service object. Defaults to `None`.

**Outputs:** `Optional[str]`
A string containing the market review report, or `None` if it fails.

**Example:**

```python
from src.services.analyzer_service import perform_market_review

# Perform market review
report = perform_market_review()
if report:
    print(report)
```

**Reference:** [`perform_market_review`](src/services/analyzer_service.py)
