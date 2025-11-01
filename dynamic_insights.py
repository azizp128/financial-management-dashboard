import streamlit as st
import pandas as pd
import re
from typing import Dict, List
from openai import OpenAI

# ==========================================================
# 🔹 Helper Function: Call OpenRouter API
# ==========================================================
def generate_ai_insights(prompt: str) -> List[str]:
    """
    Helper function to call OpenRouter API and parse the insight response.
    """
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=st.secrets["OPENROUTER_API_KEY"]
        )

        response = client.chat.completions.create(
            model="meta-llama/llama-3.1-8b-instruct",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a financial analyst AI. Provide structured, actionable insights "
                        "based on the financial data provided. Use the requested format exactly."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=500,
            temperature=0.7,
        )

        insights_text = response.choices[0].message.content

        # Parse results into list
        insights_list = [
            line.strip().strip("*-").strip()
            for line in insights_text.split("\n")
            if line.strip() and not line.lower().startswith(("analysis", "here", "based"))
        ]
        return insights_list

    except Exception as e:
        return [f"Error generating insights: {str(e)}", "Please try again later"]


# ==========================================================
# 🔹 1. Financial Trends Insights
# ==========================================================
def generate_financial_trends_insights(pnl: pd.DataFrame) -> List[str]:
    """Generate AI insights for the Financial Trends section."""
    current_period = pnl.iloc[-1]
    previous_period = pnl.iloc[-2] if len(pnl) > 1 else None

    prompt = f"""
    Analyze these financial metrics:

    Current Period ({current_period['Period']}):
    - Revenue: {current_period['Revenue']:,.2f}
    - Expenses: {current_period['Expense']:,.2f}
    - Net Profit: {current_period['Net Profit']:,.2f}
    - Margin: {current_period['Margin (%)']:.2f}%

    Previous Period ({previous_period['Period'] if previous_period is not None else 'N/A'}):
    - Revenue: {f"{previous_period['Revenue']:,.2f}" if previous_period is not None else 'N/A'}
    - Expenses: {f"{previous_period['Expense']:,.2f}" if previous_period is not None else 'N/A'}
    - Net Profit: {f"{previous_period['Net Profit']:,.2f}" if previous_period is not None else 'N/A'}
    - Margin: {f"{previous_period['Margin (%)']:.2f}" if previous_period is not None else 'N/A'}%

    Provide 3-4 concrete, actionable insights in the following format:
    - Headline Insight 1
    - Brief Explanation of the insight 1
    - Actionable Recommendation 1
    
    - Headline Insight 2
    - Brief Explanation of the insight 2
    - Actionable Recommendation 2
    """
    return generate_ai_insights(prompt)


# ==========================================================
# 🔹 2. Revenue Analysis Insights
# ==========================================================
def generate_revenue_analysis_insights(transactions: pd.DataFrame) -> List[str]:
    """Generate AI insights for the Revenue Analysis section."""
    revenue_data = transactions[transactions["Source_Type"] == "Sales"]
    top_products = revenue_data.groupby("Product")["Amount"].sum().nlargest(5)
    top_regions = revenue_data.groupby("Region")["Amount"].sum().nlargest(3)

    prompt = f"""
    Analyze these revenue metrics:

    Top 5 Products by Revenue:
    {top_products.to_string()}

    Top 3 Regions by Revenue:
    {top_regions.to_string()}

    Category Distribution:
    {revenue_data.groupby('Category')['Amount'].sum().to_string()}

    Provide 3-4 concrete, actionable insights in the following format:
    - Headline Insight 1
    - Brief Explanation of the insight 1
    - Actionable Recommendation 1
    
    - Headline Insight 2
    - Brief Explanation of the insight 2
    - Actionable Recommendation 2
    """
    return generate_ai_insights(prompt)


# ==========================================================
# 🔹 3. Expense Analysis Insights
# ==========================================================
def generate_expense_analysis_insights(transactions: pd.DataFrame) -> List[str]:
    """Generate AI insights for the Expense Analysis section."""
    expense_data = transactions[transactions["Source_Type"] == "Expense"].copy()
    expense_data["Amount"] = abs(expense_data["Amount"])

    top_expenses = expense_data.groupby("Category")["Amount"].sum().nlargest(5)

    prompt = f"""
    Analyze these expense metrics:

    Top 5 Expense Categories:
    {top_expenses.to_string()}

    Expense Trends:
    - Total Expenses: {expense_data['Amount'].sum():,.2f}
    - Average Monthly Expenses: {expense_data.groupby('Month')['Amount'].mean().mean():,.2f}
    - Highest Monthly Expense: {expense_data.groupby('Month')['Amount'].sum().max():,.2f}

    Provide 3-4 concrete, actionable insights in the following format:
    - Headline Insight 1
    - Brief Explanation of the insight 1
    - Actionable Recommendation 1
    
    - Headline Insight 2
    - Brief Explanation of the insight 2
    - Actionable Recommendation 2
    """
    return generate_ai_insights(prompt)

# Format Insights for Dashboard Display
def format_insights_for_dashboard(insights: List[str]) -> List[str]:
    formatted_text = ""
    formatted_insights = []

    current_headline_clean = ""
    brief_clean = ""
    action_clean = ""

    if not insights: # jika None atau kosong formatted_insights = "No insights available."
        formatted_insights.append("No insights available.")
        return formatted_insights

    for line in insights:
        line_clean = line.lstrip('*').strip()


        if line_clean.lower().startswith("headline insight"):
            # Simpan insight sebelumnya sebelum mulai yang baru
            if current_headline_clean:
                formatted_text += f"### {current_headline_clean}\n\n{brief_clean}\n\n{action_clean}\n\n"
                brief_clean, action_clean = "", ""

            current_headline = line_clean.split(":", 1)[-1].strip()
            current_headline_clean = re.sub(r'\*+', '', current_headline).strip()

        elif line_clean.lower().startswith("brief explanation"):
            brief = line_clean.split(":", 1)[-1].strip()
            brief_clean = re.sub(r'\*+', '', brief).strip()

        elif line_clean.lower().startswith("actionable recommendation"):
            action = line_clean.split(":", 1)[-1].strip()
            action_clean = "> 💡 **Recommendation:** " + re.sub(r'\*+', '', action).strip()

    # setelah loop selesai → tambahkan insight terakhir
    if current_headline_clean:
        formatted_text += f"### {current_headline_clean}\n\n{brief_clean}\n\n{action_clean}\n\n"
        formatted_text = formatted_text.replace('$', 'IDR ')

    formatted_insights.append(formatted_text.strip())

    return formatted_insights
