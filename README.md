# Features

- **KPI Summary:** Key metrics overview (Revenue, Expenses, Net Profit, Profit Margin, MoM Growth)
- **Financial Trends:** Visualize profit & loss, revenue, expenses, and margins over time
- **Revenue Analysis:** Drilldown by product, category, and region
- **Expense Analysis:** Breakdown by expense type and top contributors
- **Data Reconciliation:** Identify unmapped transactions and missing accounts
- **AI-Powered Insights:** Automatic, actionable recommendations for each dashboard section using OpenRouter
- **Export Reports:** Download P&L, transactions, and product performance as CSV

# How It Works

1. **Upload Data:** Sales, Expenses, and Chart of Accounts (COA) files (CSV or Excel)
2. **Automated Processing:** Data is cleaned, mapped, and merged for analysis
3. **Interactive Dashboard:** Explore trends, breakdowns, and key metrics
4. **AI Insights:** Get concrete recommendations for improving financial performance
5. **Export:** Download detailed reports for further use

# Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/azizp128/financial-management-dashboard.git
   cd financial-management-dashboard
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set your OpenRouter API key:**
   - Add your key to Streamlit secrets (secrets.toml):
     ```
     OPENROUTER_API_KEY = "your_api_key_here"
     ```

4. **Run the dashboard:**
   ```bash
   streamlit run app.py
   ```

# File Structure

```
financial-management-dashboard/
├── app.py                  # Main Streamlit dashboard
├── dynamic_insights.py     # AI-powered insights functions
├── finance_automation.py   # Data automation utilities
├── requirements.txt        # Python dependencies
├── datasets/               # Example input data
├── output/                 # Generated reports
├── README.md               # Project documentation
└── notebook.ipynb          # Data exploration notebook
```

# Data Requirements

- **Sales Data:** Transaction records (CSV/XLSX)
- **Expenses Data:** Operating expenses (CSV/XLSX)
- **Mapping COA:** Chart of Accounts mapping (CSV/XLSX)

# Customization

- Update the dashboard sections, metrics, and visualizations in `app.py`
- Modify or extend AI insight generation in `dynamic_insights.py`