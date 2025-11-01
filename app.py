import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
from dynamic_insights import (
    generate_financial_trends_insights,
    generate_revenue_analysis_insights,
    generate_expense_analysis_insights,
    format_insights_for_dashboard
)

# Page Configuration
st.set_page_config(
    page_title="Financial Dashboard",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .stMetric {
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #e1e4e8;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    h1, h2, h3 {
        color: #2c3e50;
    }
</style>
""", unsafe_allow_html=True)

# Helper Functions
@st.cache_data
def load_data(sales_file, expenses_file, coa_file):
    """Load and process data files"""
    try:
        # Load files
        if sales_file.name.endswith('.csv'):
            sales = pd.read_csv(sales_file)
        else:
            sales = pd.read_excel(sales_file)
        
        if expenses_file.name.endswith('.csv'):
            expenses = pd.read_csv(expenses_file)
        else:
            expenses = pd.read_excel(expenses_file)
        
        if coa_file.name.endswith('.csv'):
            coa = pd.read_csv(coa_file)
        else:
            coa = pd.read_excel(coa_file)
        
        return sales, expenses, coa
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return None, None, None

def prepare_transactions(sales, expenses, coa):
    """Prepare and combine transaction data"""
    # Standardize Sales
    sales = sales.rename(columns={"Total": "Amount"})
    sales["Source_Type"] = "Sales"
    sales["Description"] = None
    sales = sales[["Date", "Category", "Product", "Description", "Amount", "InvoiceNo", "Customer", "Region", "Source_Type"]]
    
    # Standardize Expenses
    expenses = expenses.rename(columns={"ExpenseType": "Category"})
    expenses["Source_Type"] = "Expense"
    expenses["InvoiceNo"] = None
    expenses["Customer"] = None
    expenses["Region"] = None
    expenses["Product"] = None
    expenses = expenses[["Date", "Category", "Product", "Description", "Amount", "InvoiceNo", "Customer", "Region", "Source_Type"]]
    
    # Remove duplicates before standardizing
    sales = sales.drop_duplicates(subset=["Date", "InvoiceNo", "Product", "Amount"], keep='first')
    expenses = expenses.drop_duplicates(subset=["Date", "Category", "Description", "Amount"], keep='first')
    coa = coa.drop_duplicates(subset=["Category", "Account"], keep='first')
    
    # Combine transactions
    transactions = pd.concat([sales, expenses], ignore_index=True)
    
    # Make expenses negative
    transactions["Amount"] = transactions.apply(
        lambda x: -x["Amount"] if x["Source_Type"] == "Expense" else x["Amount"], axis=1
    )
    
    # Type casting
    transactions['Date'] = pd.to_datetime(transactions['Date'])
    transactions['Amount'] = pd.to_numeric(transactions['Amount'], errors='coerce')
    
    # Category mapping
    category_mapping = {
        "Jewelry": "Jewelry Sales",
        "Salaries": "Salaries",
        "Supplies": "Supplies",
        "Marketing": "Marketing",
        "Delivery": "Delivery",
        "Rent": "Rent",
        "Utilities": "Utilities",
        "Product Cost": "Product Cost"
    }
    
    transactions["Category_COA"] = transactions["Category"].map(category_mapping)
    
    # Merge with COA
    transactions_merged = transactions.merge(coa, how="left", left_on="Category_COA", right_on="Category")
    transactions_merged = transactions_merged.drop(columns=["Category_y"]).rename(columns={"Category_x": "Category"})
    transactions_merged['Account'] = pd.to_numeric(transactions_merged['Account'], errors='coerce')
    
    # Safety check: Ensure no duplicate after merging
    transactions_merged = transactions_merged.drop_duplicates(
        subset=["Date", "InvoiceNo", "Amount", "Source_Type"], keep='first'
    )

    # Add time dimensions
    transactions_merged['Year'] = transactions_merged['Date'].dt.year
    transactions_merged['Month'] = transactions_merged['Date'].dt.month
    transactions_merged['Period'] = transactions_merged['Date'].dt.to_period('M').astype(str)

    # Check for unmapped categories
    mapped_categories = set(category_mapping.keys())
    existing_categories = set(transactions_merged['Category'].unique())
    unmapped_categories = existing_categories - mapped_categories

    # Check for umapped transactions
    unmapped_transactions = mapped_categories - existing_categories
    
    # Store unmapped categories for later use
    transactions_merged._unmapped_categories = unmapped_categories
    transactions_merged._unmapped_transaction = unmapped_transactions
    
    return transactions_merged

def generate_pnl(transactions, coa):
    """Generate Profit & Loss statement"""
    pnl = transactions.pivot_table(
        index=['Year', 'Month', 'Period'],
        columns='AccountType',
        values='Amount',
        aggfunc='sum',
        fill_value=0
    ).reset_index()
    
    for acct in ['Revenue', 'OPEX', 'COGS']:
        if acct not in pnl.columns:
            pnl[acct] = 0
    
    pnl['OPEX'] = abs(pnl.get('OPEX', 0))
    pnl['Expense'] = abs(pnl.get('OPEX', 0) + pnl.get('COGS', 0))
    pnl['Net Profit'] = pnl.get('Revenue', 0) - pnl['Expense']
    pnl['Margin (%)'] = (pnl['Net Profit'] / pnl['Revenue'].replace(0, 1)) * 100
    
    pnl = pnl.sort_values(['Year', 'Month'])
    
    # Check for missing accounts
    expected_types = list(set(coa['AccountType'].dropna()))
    existing_types = set(transactions['AccountType'].dropna().unique())
    missing_accounts = [acct for acct in expected_types if acct not in existing_types]
    
    # Store missing accounts for later use
    pnl._missing_accounts = missing_accounts
    
    return pnl

def calculate_mom_growth(pnl):
    """Calculate Month-over-Month growth"""
    if len(pnl) < 2:
        return 0
    
    current = pnl.iloc[-1]['Revenue']
    previous = pnl.iloc[-2]['Revenue']
    
    if previous == 0:
        return 0
    
    return ((current - previous) / previous) * 100

# Main App
def main():
    st.title("💰 Financial Management Dashboard")
    st.markdown("---")
    
    # Sidebar - File Upload
    with st.sidebar:
        st.header("📁 Data Upload")
        st.subheader('Upload your data here')
        
        sales_file = st.file_uploader("Upload Sales Data", type=['xlsx', 'csv'], key='sales')
        expenses_file = st.file_uploader("Upload Expenses Data", type=['xlsx', 'csv'], key='expenses')
        coa_file = st.file_uploader("Upload Mapping COA", type=['xlsx', 'csv'], key='coa')
        
        st.markdown("---")
        st.markdown("### 📊 Dashboard Sections")
        st.markdown("""
        - **KPI Summary**: Key metrics overview
        - **Financial Trends**: Revenue, expenses, margins
        - **Revenue Analysis**: Product, category, region breakdowns
        - **Expense Analysis**: Expense types & contributors
        - **Data Reconciliation**: Identify data issues
        - **Export Reports**: Download results
        """)
    
    # Check if all files are uploaded
    if not all([sales_file, expenses_file, coa_file]):
        st.info("👈 Please upload all required files to begin analysis")
        st.markdown("""
        ### Required Files
        1. **Sales Data** - Transaction sales records
        2. **Expenses Data** - Operating expenses
        3. **Mapping COA** - Chart of Accounts mapping
        """)
        sales_sample = pd.read_excel("datasets/sales.xlsx").sample(100)
        expenses_sample = pd.read_excel("datasets/expenses.xlsx").sample(100)
        coa_sample = pd.read_excel("datasets/mapping_coa.xlsx")

        st.subheader("Sample Data Format")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Sales Data Sample**")
            st.dataframe(sales_sample, use_container_width=True)
            st.download_button("Download Sample Sales Data", data=sales_sample.to_csv(index=False), file_name="sample_sales_data.csv", mime="text/csv", type="primary")
        with col2:
            st.markdown("**Expenses Data Sample**")
            st.dataframe(expenses_sample, use_container_width=True)
            st.download_button("Download Sample Expenses Data", data=expenses_sample.to_csv(index=False), file_name="sample_expenses_data.csv", mime="text/csv", type="primary")
        with col3:
            st.markdown("**Mapping COA Sample**")
            st.dataframe(coa_sample, use_container_width=True)
            st.download_button("Download Sample COA Data", data=coa_sample.to_csv(index=False), file_name="sample_coa_data.csv", mime="text/csv", type="primary")
        return
    
    # Load and process data
    with st.spinner("Processing data..."):
        sales, expenses, coa = load_data(sales_file, expenses_file, coa_file)
        
        if sales is None or expenses is None or coa is None:
            st.error("Failed to load data. Please check file formats.")
            return
        
        transactions = prepare_transactions(sales, expenses, coa)
        pnl = generate_pnl(transactions, coa)

        # Extract data quality issues
        unmapped_categories = getattr(transactions, '_unmapped_categories', set())
        unmapped_transactions = getattr(transactions, '_unmapped_transaction', set())
        missing_accounts = getattr(pnl, '_missing_accounts', [])

        if "financial_insights" not in st.session_state:
            st.session_state.financial_insights = None
        if "revenue_insights" not in st.session_state:
            st.session_state.revenue_insights = None
        if "expense_insights" not in st.session_state:
            st.session_state.expense_insights = None
    
    # === KPI SUMMARY SECTION ===
    st.header("📈 Key Performance Indicators")
    
    # Calculate KPIs
    total_revenue = pnl['Revenue'].sum()
    total_expense = pnl['Expense'].sum()
    net_profit = pnl['Net Profit'].sum()
    profit_margin = (net_profit/total_revenue) * 100
    mom_growth = calculate_mom_growth(pnl)
    
    # Display KPIs in columns
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            label="💵 Total Revenue",
            value=f"IDR {total_revenue:,.0f}",
            delta=f"{mom_growth:.1f}% MoM" if mom_growth != 0 else None
        )
    
    with col2:
        expense_rev_ratio = (total_expense / total_revenue * 100) if total_revenue != 0 else 0
        st.metric(
            label="💸 Total Expense",
            value=f"IDR {total_expense:,.0f}",
            delta=f"{expense_rev_ratio:.1f}% of Revenue" if expense_rev_ratio != 0 else None
        )
    
    with col3:
        st.metric(
            label="💰 Net Profit",
            value=f"IDR {net_profit:,.0f}",
            delta="Profitable" if net_profit > 0 else "-Loss"
        )
    
    with col4:
        st.metric(
            label="📊 Profit Margin",
            value=f"{profit_margin:.1f}%",
            delta="Healthy" if profit_margin > 20 else "-Needs Improvement" # Simple threshold for margin health
        )
    with col5:
        st.metric(
            label="📈 MoM Growth",
            value=f"{mom_growth:.1f}%",
            delta=f"Growing" if mom_growth > 0 else f"-Declining",
        )
    
    st.markdown("---")
    
    # === FINANCIAL TRENDS SECTION ===
    st.header("📊 Financial Trends")
    tab1, tab2, tab3 = st.tabs([
        "Profit & Loss Overview",
        "Revenue vs Expense Over Time",
        "Key Insights"
    ])

    with tab1:
        st.subheader("Profit & Loss Overview")

        # Reorder PnL columns for better display
        new_order = ['Year', 'Month', 'Period', 'Revenue', 'COGS', 'OPEX', 'Expense', 'Net Profit', 'Margin (%)']
        pnl = pnl[new_order]
        st.dataframe(pnl, use_container_width=True)
    
    with tab2:
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("Revenue, Expense & Net Profit Over Time")
            
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            fig.add_trace(
                go.Scatter(
                    x=pnl['Period'],
                    y=pnl['Revenue'],
                    name="Revenue",
                    line=dict(color='#2E86DE', width=3),
                    mode='lines+markers'
                ),
                secondary_y=False
            )

            fig.add_trace(
                go.Scatter(
                    x=pnl['Period'],
                    y=pnl['Expense'],
                    name="Expense",
                    line=dict(color="#DE342E", width=3),
                    mode='lines+markers'
                ),
                secondary_y=False
            )
            
            fig.add_trace(
                go.Scatter(
                    x=pnl['Period'],
                    y=pnl['Net Profit'],
                    name="Net Profit",
                    line=dict(color='#10AC84', width=3),
                    mode='lines+markers'
                ),
                secondary_y=False
            )
            
            fig.add_trace(
                go.Scatter(
                    x=pnl['Period'],
                    y=pnl['Margin (%)'],
                    name="Margin (%)",
                    line=dict(color='#F79F1F', width=2, dash='dash'),
                    mode='lines+markers'
                ),
                secondary_y=True
            )
            
            fig.update_xaxes(title_text="Period")
            fig.update_yaxes(title_text="Amount (IDR)", secondary_y=False)
            fig.update_yaxes(title_text="Margin (%)", secondary_y=True)
            fig.update_layout(height=400, hovermode='x unified')
            # fig.update_yaxes(rangemode='tozero', secondary_y=False)
            fig.update_yaxes(rangemode='tozero', secondary_y=True)
            
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Period Performance")
            
            # Best and worst periods
            best_period = pnl.loc[pnl['Net Profit'].idxmax()]
            worst_period = pnl.loc[pnl['Net Profit'].idxmin()]
            
            st.markdown(f"""
            **🏆 Best Period:**  
            {best_period['Period']}  
            Profit: IDR {best_period['Net Profit']:,.0f}
            
            **📉 Worst Period:**  
            {worst_period['Period']}  
            Profit: IDR {worst_period['Net Profit']:,.0f}
            
            **📊 Trend Analysis:**  
            - Avg Revenue: IDR {pnl['Revenue'].mean():,.0f}
            - Avg Expense: IDR {pnl['Expense'].mean():,.0f}
            - Revenue Volatility: {pnl['Revenue'].std() / pnl['Revenue'].mean() * 100:.1f}%
            """) # Revenue Volatility is Coefficient of Variation
    
    with tab3:
        # Key Insights
        st.subheader("Key Financial Insights")
        
        if st.button("🔁 Generate Financial Insights", key="btn_financial", type="primary"):
            if "financial_insights" in st.session_state:
                del st.session_state["financial_insights"]
            
            with st.spinner("Generating Financial Insights..."):
                insights = generate_financial_trends_insights(pnl)
                st.session_state["financial_insights"] = insights
                st.success("✅ Financial insights updated!")

        # Tampilkan hasil jika sudah ada di session_state
        if "financial_insights" in st.session_state:
            formatted = format_insights_for_dashboard(st.session_state["financial_insights"])
            st.markdown(formatted[0])
            # st.write(st.session_state["financial_insights"])

    st.markdown("---")
    # === DRILLDOWN REVENUE ANALYSIS SECTION ===
    st.header("💰 Revenue Analysis")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "Revenue Overview",
        "Revenue Breakdown",
        "Top Contributors",
        "Key Insights"
    ])
    
    with tab1:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Revenue by Category")
            revenue_data = transactions[transactions['Source_Type'] == 'Sales']
            rev_by_cat = revenue_data.groupby('Category')['Amount'].sum().reset_index()
            rev_by_cat = rev_by_cat.sort_values('Amount', ascending=False)
            
            fig = px.pie(
                rev_by_cat,
                values='Amount',
                names='Category'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Revenue by Region")
            rev_by_region = revenue_data.groupby('Region')['Amount'].sum().reset_index()
            rev_by_region = rev_by_region.sort_values('Amount', ascending=True)
            
            fig = px.bar(
                rev_by_region,
                x='Amount',
                y='Region',
                orientation='h',
                color='Amount',
                color_continuous_scale='Blues'
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        product_data = transactions[transactions['Source_Type'] == 'Sales'].copy()
        product_perf = product_data.groupby('Product').agg({
            'Amount': 'sum',
            'InvoiceNo': 'count'
        }).reset_index()
        product_perf.columns = ['Product', 'Revenue', 'Transactions']
        product_perf = product_perf.sort_values('Revenue', ascending=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Top 10 Products by Revenue")
            fig = px.bar(
                product_perf.head(10),
                x='Revenue',
                y='Product',
                orientation='h',
                color='Revenue',
                color_continuous_scale='Greens'
            )
            fig.update_xaxes(tickangle=0)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Revenue vs Transaction Volume")
            fig = px.scatter(
                product_perf,
                x='Transactions',
                y='Revenue',
                size='Revenue',
                hover_data=['Product'],
                color='Revenue',
                color_continuous_scale='Viridis'
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Top 5 Revenue Generators")
            top_products = product_perf.head(5)
            
            for idx, row in top_products.sort_values(by='Revenue', ascending=False).iterrows():
                st.markdown(f"""
                **{row['Product']}**  
                Revenue: IDR {row['Revenue']:,.0f} | Transactions: {row['Transactions']}
                """)
                st.progress(row['Revenue'] / product_perf['Revenue'].sum())
        
        with col2:
            st.subheader("Bottom 5 Products")
            bottom_products = product_perf.tail(5)
            
            for idx, row in bottom_products.iterrows():
                st.markdown(f"""
                **{row['Product']}**  
                Revenue: IDR {row['Revenue']:,.0f} | Transactions: {row['Transactions']}
                """)
                st.progress(row['Revenue'] / product_perf['Revenue'].sum())
    
    with tab4:
        st.subheader("Key Revenue Insights")
        if st.button("🔁 Generate Revenue Insights", key="btn_revenue", type="primary"):
            
            # Clear previous insights
            if "revenue_insights" in st.session_state:
                del st.session_state["revenue_insights"]
            
            with st.spinner("Generating Revenue Insights..."):
                insights = generate_revenue_analysis_insights(transactions)
                st.session_state["revenue_insights"] = insights
                st.success("✅ Revenue insights updated!")

        if "revenue_insights" in st.session_state:
            formatted = format_insights_for_dashboard(st.session_state["revenue_insights"])
            st.markdown(formatted[0])
            # st.write(st.session_state["revenue_insights"])

    
    st.markdown("---")
    st.header("💸 Expense Analysis")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "Expense Overview",
        "Expense Breakdown",
        "Top Contributors",
        "Key Insights"
    ])

    expense_data = transactions[transactions['Source_Type'] == 'Expense'].copy()
    expense_data['Amount'] = abs(expense_data['Amount'])

    # Expense Breakdown Tabs
    with tab1:
        col1, col2 = st.columns(2)
        
        # Expense by Type
        with col1:
            st.subheader("Expenses by Type")
            exp_by_type = expense_data.groupby('AccountType')['Amount'].sum().sort_values(ascending=False).reset_index()
            exp_by_type = exp_by_type.sort_values('Amount', ascending=False)
            
            fig = px.bar(
                    exp_by_type,
                    x="AccountType",
                    y="Amount",
                    labels={'Amount': 'Amount (IDR)', 'Period': 'Period'},
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
            fig.update_layout(height=400, barmode='group')
            st.plotly_chart(fig, use_container_width=True)

        # Expense Breakdown
        with col2:
            st.subheader("Monthly Expenses by Category")
            expense_by_category = expense_data.groupby(['Period', 'Category'])['Amount'].sum().sort_values(ascending=False).reset_index()
            
            fig = px.bar(
                expense_by_category,
                x='Period',
                y='Amount',
                color='Category',
                labels={'Amount': 'Amount (IDR)', 'Period': 'Period'},
                color_discrete_sequence=px.colors.qualitative.Set3
            )
            fig.update_layout(height=400, barmode='group')
            st.plotly_chart(fig, use_container_width=True)
        
    with tab2:
        if 'AccountType' in expense_data.columns:

            # Define expense types excluding Revenue
            expense_type = [col for col in transactions['AccountType'].unique().tolist() if col != 'Revenue']
            
            visuals = []
            
            # Loop through each expense type for monthly breakdown
            for etype in expense_type:
                data = transactions[transactions['AccountType'] == etype].copy()
                if not data.empty:
                    data['Amount'] = abs(data['Amount'])
                    data_by_category = data.groupby(['Period', 'Category'])['Amount'].sum().reset_index()
                    
                    visuals.append({
                        "title": f"Monthly {etype} by Category",
                        "data": data_by_category,
                        "x": "Period",
                        "y": "Amount",
                        "color": "Category",
                        "type": etype
                    })
            
            # Create columns dynamically based on number of visuals
            cols = st.columns(len(visuals))
            
            # Generate each visualization
            for col, viz in zip(cols, visuals):
                with col:
                    st.subheader(viz["title"])
                    fig = px.bar(
                        viz["data"],
                        x=viz["x"],
                        y=viz["y"],
                        color=viz["color"],
                        labels={'Amount': 'Amount (IDR)', 'Period': 'Period'},
                        color_discrete_sequence=px.colors.qualitative.Set3
                    )
                    fig.update_layout(height=400, barmode='group')
                    st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        st.subheader("Top Expense Contributors")
        top_expense_category = expense_data.groupby('Category').agg({
            'Amount': 'sum'
        }).reset_index()
        
        for idx, row in top_expense_category.sort_values(by='Amount', ascending=False).iterrows():
            st.markdown(f"""
            **{row['Category']}**  
            Amount: IDR {row['Amount']:,.0f}
            """)
            st.progress(row['Amount'] / expense_data['Amount'].sum())
    
    with tab4:
        st.subheader("Key Expense Insights")

        if st.button("🔁 Generate Expense Insights", key="btn_expense", type="primary"):
            if "expense_insights" in st.session_state:
                del st.session_state["expense_insights"]

            with st.spinner("Generating Expense Insights..."):
                insights = generate_expense_analysis_insights(transactions)
                st.session_state["expense_insights"] = insights
                st.success("✅ Expense insights updated!")

        if "expense_insights" in st.session_state:
            formatted = format_insights_for_dashboard(st.session_state["expense_insights"])
            st.markdown(formatted[0])
            # st.write(st.session_state["expense_insights"])
    
    st.markdown("---")


    # === DATA RECONCILIATION SECTION (CONDITIONAL) ===
    if unmapped_categories or missing_accounts or unmapped_transactions:
        st.header("⚠️ Data Reconciliation Issues")
        
        st.warning("""
        **Attention Required:** Data quality issues have been detected that may affect report accuracy.
        Please review and address the following issues:
        """)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Check for unmapped categories
            if unmapped_categories:
                st.error(f"**🔴 {len(unmapped_categories)} Unmapped Categories Found**")
                st.markdown("""
                These categories exist in your transaction data but are not mapped in the Chart of Accounts.
                This may cause incomplete financial reporting.
                """)
                
                unmapped_df = pd.DataFrame({
                    'Category': sorted(list(unmapped_categories)),
                    'Status': ['Not Mapped'] * len(unmapped_categories),
                    'Impact': ['Financial data not categorized'] * len(unmapped_categories)
                })
                
                st.dataframe(unmapped_df, use_container_width=True, height=200)
                
                # Count transactions affected
                affected_transactions = transactions[transactions['Category'].isin(unmapped_categories)]
                affected_amount = abs(affected_transactions['Amount'].sum())
                
                st.metric(
                    label="Affected Transactions",
                    value=f"{len(affected_transactions)} transactions",
                    delta=f"IDR {affected_amount:,.0f} total amount"
                )
                
                # Download button for unmapped categories
                unmapped_csv = unmapped_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Unmapped Categories",
                    data=unmapped_csv,
                    file_name=f"Unmapped_Categories_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    type="primary"
                )
            else:
                st.success("**✅ All Categories Mapped**")
                st.markdown("All transaction categories are properly mapped to the Chart of Accounts.")
        
        with col2:
            # Check for missing account types
            if missing_accounts:
                st.error(f"**🔴 {len(missing_accounts)} Missing Account Types**")
                st.markdown("""
                These account types are defined in your COA but have no transactions this period.
                This may indicate missing data or inactive accounts.
                """)
                
                missing_df = pd.DataFrame({
                    'Account Type': sorted(missing_accounts),
                    'Status': ['No Transactions'] * len(missing_accounts),
                    'Recommendation': ['Verify if transactions exist'] * len(missing_accounts)
                })
                
                st.dataframe(missing_df, use_container_width=True, height=200)
                
                st.info("""
                **Note:** Missing account types may be expected if:
                - The account is not active this period
                - It's a new account with no history yet
                - Certain expense types don't occur every month
                """)
                
                # Download button for missing accounts
                missing_csv = missing_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Missing Accounts",
                    data=missing_csv,
                    file_name=f"Missing_Accounts_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    type="primary"
                )
            else:
                st.success("**✅ All Account Types Active**")
                st.markdown("All expected account types have transactions in this period.")
        
        with col3:
            # Check for unmapped transactions
            if unmapped_transactions:
                st.warning(f"**⚠️ {len(unmapped_transactions)} Categories Missing in Transactions**")
                st.markdown("""
                These categories exist in your COA but have no transactions this period.
                This helps identify accounts or categories that are inactive or missing data.
                """)

                # Create DataFrame for display
                missing_cat_df = pd.DataFrame({
                    'Category': sorted(list(unmapped_transactions)),
                    'Status': ['No Transactions'] * len(unmapped_transactions),
                    'Recommendation': ['Verify if transactions exist'] * len(unmapped_transactions)
                })

                st.dataframe(missing_cat_df, use_container_width=True, height=200)

                st.info("""
                **Note:** Categories missing in transactions may be expected if:
                - The category is not active this period
                - It's a new category with no history yet
                - Certain categories don't incur transactions every month
                """)

                # Download CSV
                missing_cat_csv = missing_cat_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Missing Categories",
                    data=missing_cat_csv,
                    file_name=f"Missing_Categories_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv",
                    type="primary"
                )
            else:
                st.success("**✅ All Categories Have Transactions**")
                st.markdown("All COA categories have transactions in this period.")

        # Combined reconciliation report
        st.markdown("---")
        st.subheader("📋 Complete Reconciliation Report")
        
        reconciliation_summary = {
            'Issue Type': [],
            'Missing': [],
            'Count': [],
            'Severity': [],
            'Action Required': []
        }
        
        if unmapped_categories:
            reconciliation_summary['Issue Type'].append('Unmapped Categories')
            reconciliation_summary['Missing'].append(list(unmapped_categories))
            reconciliation_summary['Count'].append(len(unmapped_categories))
            reconciliation_summary['Severity'].append('High')
            reconciliation_summary['Action Required'].append('Add mappings to COA')
        
        if missing_accounts:
            reconciliation_summary['Issue Type'].append('Missing Account Types')
            reconciliation_summary['Missing'].append(list(missing_accounts))
            reconciliation_summary['Count'].append(len(missing_accounts))
            reconciliation_summary['Severity'].append('Medium')
            reconciliation_summary['Action Required'].append('Verify transaction completeness')
        
        if unmapped_transactions:
            reconciliation_summary['Issue Type'].append('Categories Missing in Transactions')
            reconciliation_summary['Missing'].append(list(unmapped_transactions))
            reconciliation_summary['Count'].append(len(unmapped_transactions))
            reconciliation_summary['Severity'].append('Low')
            reconciliation_summary['Action Required'].append('Check for inactive categories')
        
        summary_df = pd.DataFrame(reconciliation_summary)
        st.dataframe(summary_df, use_container_width=True)
        
        # Combined download
        col1, col2, col3 = st.columns(3)
        with col2:
            # Create combined reconciliation file
            with pd.ExcelWriter('reconciliation_report.xlsx', engine='openpyxl') as writer:
                if unmapped_categories:
                    unmapped_df.to_excel(writer, sheet_name='Unmapped Categories', index=False)
                    affected_transactions.to_excel(writer, sheet_name='Affected Transactions', index=False)
                
                if missing_accounts:
                    missing_df.to_excel(writer, sheet_name='Missing Accounts', index=False)

                if unmapped_transactions:
                    missing_cat_df.to_excel(writer, sheet_name='Missing Categories', index=False)
                
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            with open('reconciliation_report.xlsx', 'rb') as f:
                st.download_button(
                    label="📥 Download Complete Reconciliation Report",
                    data=f,
                    file_name=f"Reconciliation_Report_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )
        
        st.markdown("---")
    
    # === EXPORT SECTION ===
    st.header("📥 Export Reports")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Export PnL
        st.subheader("Profit & Loss Report")
        pnl_csv = pnl.to_csv(index=False)
        st.dataframe(pnl, use_container_width=True)
        st.download_button(
            label="Download P&L Report",
            data=pnl_csv,
            file_name=f"PnL_Report_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    with col2:
        # Export Transactions
        st.subheader("Transaction Details")
        trans_csv = transactions.to_csv(index=False)
        st.dataframe(transactions, use_container_width=True)
        st.download_button(
            label="Download Transaction Details",
            data=trans_csv,
            file_name=f"Transactions_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    with col3:
        # Export Product Performance
        st.subheader("Product Performance")
        prod_csv = product_perf.to_csv(index=False)
        st.dataframe(product_perf, use_container_width=True)
        st.download_button(
            label="Download Product Performance",
            data=prod_csv,
            file_name=f"Product_Performance_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #7f8c8d;'>
        <p>Financial Management Dashboard | Developed by Aziz Prabowo</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()