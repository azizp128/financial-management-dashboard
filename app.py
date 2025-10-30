import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

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
    
    # Add time dimensions
    transactions_merged['Year'] = transactions_merged['Date'].dt.year
    transactions_merged['Month'] = transactions_merged['Date'].dt.month
    transactions_merged['Period'] = transactions_merged['Date'].dt.to_period('M').astype(str)
    
    return transactions_merged

def generate_pnl(transactions):
    """Generate Profit & Loss statement"""
    coa_types = transactions['AccountType'].dropna().unique()
    
    pnl = transactions.pivot_table(
        index=['Year', 'Month', 'Period'],
        columns='AccountType',
        values='Amount',
        aggfunc='sum',
        fill_value=0
    ).reset_index()
    
    # Ensure all account types exist
    for acct in ['Revenue', 'OPEX', 'COGS']:
        if acct not in pnl.columns:
            pnl[acct] = 0
    
    # Calculate metrics
    pnl['Expense'] = abs(pnl.get('OPEX', 0) + pnl.get('COGS', 0))
    pnl['Net Profit'] = pnl.get('Revenue', 0) - pnl['Expense']
    pnl['Margin (%)'] = (pnl['Net Profit'] / pnl['Revenue'].replace(0, 1)) * 100
    
    # Sort by period
    pnl = pnl.sort_values(['Year', 'Month'])
    
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
        - **Drilldown Analysis**: Detailed breakdowns
        - **Export Reports**: Download results
        """)
    
    # Check if all files are uploaded
    if not all([sales_file, expenses_file, coa_file]):
        st.info("👈 Please upload all required files to begin analysis")
        st.markdown("""
        ### Required Files:
        1. **Sales Data** - Transaction sales records
        2. **Expenses Data** - Operating expenses
        3. **Mapping COA** - Chart of Accounts mapping
        """)
        return
    
    # Load and process data
    with st.spinner("Processing data..."):
        sales, expenses, coa = load_data(sales_file, expenses_file, coa_file)
        
        if sales is None or expenses is None or coa is None:
            st.error("Failed to load data. Please check file formats.")
            return
        
        transactions = prepare_transactions(sales, expenses, coa)
        pnl = generate_pnl(transactions)
    
    # === KPI SUMMARY SECTION ===
    st.header("📈 Key Performance Indicators")
    
    # Calculate KPIs
    total_revenue = pnl['Revenue'].sum()
    total_expense = pnl['Expense'].sum()
    net_profit = pnl['Net Profit'].sum()
    avg_margin = pnl['Margin (%)'].mean()
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
        st.metric(
            label="💸 Total Expense",
            value=f"IDR {total_expense:,.0f}",
            delta=f"{(total_expense/total_revenue*100):.1f}% of Revenue"
        )
    
    with col3:
        profit_color = "normal" if net_profit >= 0 else "inverse"
        st.metric(
            label="💰 Net Profit",
            value=f"IDR {net_profit:,.0f}",
            delta="Profitable" if net_profit >= 0 else "Loss"
        )
    
    with col4:
        st.metric(
            label="📊 Profit Margin",
            value=f"{avg_margin:.1f}%",
            delta="Healthy" if avg_margin > 20 else "Needs Improvement"
        )
    
    with col5:
        st.metric(
            label="📈 MoM Growth",
            value=f"{mom_growth:.1f}%",
            delta="Growing" if mom_growth > 0 else "Declining"
        )
    
    st.markdown("---")
    
    # === FINANCIAL TRENDS SECTION ===
    st.header("📊 Financial Trends")
    
    # Revenue vs Net Profit Chart
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Revenue vs Net Profit Over Time")
        
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
        """)
    
    # Expense Breakdown
    st.subheader("Expense Breakdown by Category")
    
    expense_data = transactions[transactions['Source_Type'] == 'Expense'].copy()
    expense_data['Amount'] = abs(expense_data['Amount'])
    
    expense_by_category = expense_data.groupby(['Period', 'Category'])['Amount'].sum().reset_index()
    
    fig = px.bar(
        expense_by_category,
        x='Period',
        y='Amount',
        color='Category',
        title="Monthly Expenses by Category (Stacked)",
        labels={'Amount': 'Amount (IDR)', 'Period': 'Period'},
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    fig.update_layout(height=400)
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # === DRILLDOWN ANALYSIS SECTION ===
    st.header("🔍 Detailed Analysis")
    
    tab1, tab2, tab3, tab4 = st.tabs([
        "Revenue Breakdown",
        "Expense Analysis",
        "Product Performance",
        "Top Contributors"
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
                names='Category',
                title="Revenue Distribution by Category"
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
                title="Revenue by Region",
                color='Amount',
                color_continuous_scale='Blues'
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.subheader("Expense Analysis by Type")
        
        if 'AccountType' in expense_data.columns:
            exp_by_type = expense_data.groupby('AccountType')['Amount'].sum().reset_index()
            exp_by_type = exp_by_type.sort_values('Amount', ascending=False)
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig = px.bar(
                    exp_by_type,
                    x='AccountType',
                    y='Amount',
                    title="Total Expenses by Type",
                    color='Amount',
                    color_continuous_scale='Reds'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("#### Table View")
                st.dataframe(
                    exp_by_type.style.format({'Amount': 'IDR {:,.0f}'}),
                    use_container_width=True,
                    height=300
                )
    
    with tab3:
        st.subheader("Product Performance Analysis")
        
        product_data = transactions[transactions['Source_Type'] == 'Sales'].copy()
        product_perf = product_data.groupby('Product').agg({
            'Amount': 'sum',
            'InvoiceNo': 'count'
        }).reset_index()
        product_perf.columns = ['Product', 'Revenue', 'Transactions']
        product_perf = product_perf.sort_values('Revenue', ascending=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig = px.bar(
                product_perf.head(10),
                x='Revenue',
                y='Product',
                orientation='h',
                title="Top 10 Products by Revenue",
                color='Revenue',
                color_continuous_scale='Greens'
            )
            fig.update_xaxes(tickangle=0)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            fig = px.scatter(
                product_perf,
                x='Transactions',
                y='Revenue',
                size='Revenue',
                hover_data=['Product'],
                title="Revenue vs Transaction Volume",
                color='Revenue',
                color_continuous_scale='Viridis'
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
        st.subheader("Top & Bottom Contributors")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 🏆 Top 5 Revenue Generators")
            top_products = product_perf.head(5)
            
            for idx, row in top_products.iterrows():
                st.markdown(f"""
                **{row['Product']}**  
                Revenue: IDR {row['Revenue']:,.0f} | Transactions: {row['Transactions']}
                """)
                st.progress(row['Revenue'] / product_perf['Revenue'].max())
        
        with col2:
            st.markdown("### 📉 Bottom 5 Products")
            bottom_products = product_perf.tail(5)
            
            for idx, row in bottom_products.iterrows():
                st.markdown(f"""
                **{row['Product']}**  
                Revenue: IDR {row['Revenue']:,.0f} | Transactions: {row['Transactions']}
                """)
                st.progress(row['Revenue'] / product_perf['Revenue'].max())
    
    st.markdown("---")
    
    # === EXPORT SECTION ===
    st.header("📥 Export Reports")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Export PnL
        pnl_csv = pnl.to_csv(index=False)
        st.download_button(
            label="Download P&L Report",
            data=pnl_csv,
            file_name=f"PnL_Report_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    with col2:
        # Export Transactions
        trans_csv = transactions.to_csv(index=False)
        st.download_button(
            label="Download Transaction Details",
            data=trans_csv,
            file_name=f"Transactions_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    
    with col3:
        # Export Product Performance
        prod_csv = product_perf.to_csv(index=False)
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
        <p>Financial Management Dashboard | Generated: {}</p>
    </div>
    """.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')), unsafe_allow_html=True)

if __name__ == "__main__":
    main()