import pandas as pd
import matplotlib.pyplot as plt

# --- CONFIG ---
INPUT_FILES = {
    'sales': 'sales.xlsx',
    'expenses': 'expenses.xlsx',
    'coa': 'mapping_coa.xlsx'
}
OUTPUT_FILE = 'output/finance_report_automation.xlsx'
CHART_FILE = 'output/revenue_vs_profit.png'

# --- PART 1: DATA PREPARATION ---
def load_and_clean_data():
    # Load data
    sales = pd.read_excel(f"datasets/{INPUT_FILES['sales']}")
    expenses = pd.read_excel(f"datasets/{INPUT_FILES['expenses']}")
    coa = pd.read_excel(f"datasets/{INPUT_FILES['coa']}")

    # Standardize Sales
    sales = sales.rename(columns={
        "Total": "Amount"
    })
    sales["Source_Type"] = "Sales"
    sales["Description"] = None

    # Pilih kolom relevan dan tambahkan kolom kosong agar sama dengan Expenses
    sales = sales[["Date", "Category", "Product", "Description", "Amount", "InvoiceNo", "Customer", "Region", "Source_Type"]]

    # Standardize Expenses
    expenses = expenses.rename(columns={
        "ExpenseType": "Category"
    })
    expenses["Source_Type"] = "Expense"
    expenses["InvoiceNo"] = None
    expenses["Customer"] = None
    expenses["Region"] = None
    expenses["Product"] = None

    expenses = expenses[["Date", "Category", "Product", "Description", "Amount", "InvoiceNo", "Customer", "Region", "Source_Type"]]
    
    # Combine (Append)
    transactions = pd.concat([sales, expenses], ignore_index=True)

    # ubah expense menjadi negatif
    transactions["Amount"] = transactions.apply(
        lambda x: -x["Amount"] if x["Source_Type"] == "Expense" else x["Amount"], axis=1
    )

    # Type Casting
    transactions['Date'] = pd.to_datetime(transactions['Date'])
    transactions['Amount'] = pd.to_numeric(transactions['Amount'], errors='coerce')

    # Buat mapping manual
    category_mapping = {
        "Jewelry": "Jewelry Sales",     # dari Sales
        "Salaries": "Salaries",
        "Supplies": "Supplies",
        "Marketing": "Marketing",
        "Delivery": "Delivery",
        "Rent": "Rent",
        "Utilities": "Utilities",
        "Product Cost": "Product Cost" # Tidak ada match
    }

    # Buat kolom kategori baru untuk merge
    transactions["Category_COA"] = transactions["Category"].map(category_mapping)

    # Merge dengan COA
    transactions_merged = transactions.merge(coa, how="left", left_on="Category_COA", right_on="Category")

    # Hapus duplikat kolom Category dari COA (optional)
    transactions_merged = transactions_merged.drop(columns=["Category_y"]).rename(columns={"Category_x":"Category"})

    # Type Casting kolom Account
    transactions_merged['Account'] = pd.to_numeric(transactions_merged['Account'], errors='coerce')

    # Add year & month
    transactions_merged['Year'] = transactions_merged['Date'].dt.year
    transactions_merged['Month'] = transactions_merged['Date'].dt.month

    # Peringatan kalau ada transaksi tanpa mapping
    mapped_categories = set(category_mapping.keys())
    existing_categories = set(transactions_merged['Category'].unique())
    unmapped_categories = existing_categories - mapped_categories
    output_unmapped_categories = pd.DataFrame({'Category': list(unmapped_categories)})

    if unmapped_categories:
        print("⚠️ Peringatan: Ada transaksi yang tidak terpetakan di COA!\n\tDaftar kategori belum terpetakan:", list(unmapped_categories))
        output_unmapped_categories.to_csv("output/unmapped_transactions.csv", index=False)
        print("👉 Disimpan di unmapped_transactions.csv untuk review.")

    return transactions_merged

# --- PART 2: AUTOMATED P&L ---
def generate_pnl(transactions):
    # Daftar AccountType yang diharapkan (berdasarkan COA)
    expected_types = list(set(pd.read_excel(f"datasets/{INPUT_FILES['coa']}")['AccountType']))  # ['Revenue', 'OPEX', 'COGS']

    # Deteksi akun yang diharapkan tapi tidak ada di transaksi
    missing_accounts = [acct for acct in expected_types if acct not in transactions['AccountType'].unique()]

    if missing_accounts:
        print("⚠️ Warning: Ada akun yang tidak muncul di transaksi bulan ini:", missing_accounts)
    else:
        print("✅ Semua akun utama (Revenue, OPEX, COGS) ada di data transaksi.")

    # Pivot transaksi berdasarkan AccountType
    pnl = transactions.pivot_table(
        index=['Year', 'Month'],
        columns='AccountType',
        values='Amount',
        aggfunc='sum',
        fill_value=0
    ).reset_index()
    pnl.columns.name = None

    # Pastikan semua tipe akun yang diharapkan muncul, walaupun 0
    for acct in expected_types:
        if acct not in pnl.columns:
            pnl[acct] = 0  # tambahkan kolom kosong

    # Hitung Expense = OPEX + COGS
    pnl['Expense'] = abs(pnl['OPEX'] + pnl['COGS'])

    # Hitung Net Profit = Revenue - Expense
    pnl['Net Profit'] = pnl['Revenue'] - pnl['Expense']

    # Tambahkan kolom periode (untuk visualisasi)
    pnl['Period'] = pd.to_datetime(pnl[['Year','Month']].assign(day=1)).dt.strftime('%b %Y')

    # Urutkan kolom dengan urutan yang lebih logis
    cols = ['Period', 'Revenue', 'Expense', 'Net Profit']
    for c in pnl.columns:
        if c not in cols:
            cols.append(c)

    pnl_final = pnl[cols].copy()
    
    return pnl_final

# --- PART 3: VISUALIZATION & INSIGHTS ---
def plot_and_save(pnl_df, filename=CHART_FILE, title="Monthly Revenue, Net Profit & Margin Analysis", dpi=300):
    # Validate data
    required_cols = ['Period', 'Revenue', 'Net Profit']
    missing_cols = [col for col in required_cols if col not in pnl_df.columns]
    
    if missing_cols:
        raise ValueError(f"Missing required columns: {missing_cols}")
    
    # Create figure with two y-axes
    fig, ax1 = plt.subplots(figsize=(14, 7))
    ax2 = ax1.twinx()
    
    # Color scheme
    colors = {
        'revenue': '#2E86DE',
        'profit': '#10AC84',
        'loss': '#EE5A6F',
        'margin': '#F79F1F',
    }
    
    # Prepare x-axis
    x = range(len(pnl_df))
    x_labels = pnl_df['Period'].tolist()
    
    # Plot Revenue
    line1 = ax1.plot(x, pnl_df['Revenue'], 
                     color=colors['revenue'], 
                     linewidth=3, 
                     marker='o', 
                     markersize=10,
                     markerfacecolor=colors['revenue'],
                     markeredgecolor='white',
                     markeredgewidth=2,
                     label='Revenue',
                     zorder=3)
    
    # Fill under Revenue line
    ax1.fill_between(x, pnl_df['Revenue'], alpha=0.1, color=colors['revenue'])
    
    # Plot Net Profit with conditional colors
    profit_colors = [colors['profit'] if p >= 0 else colors['loss'] 
                     for p in pnl_df['Net Profit']]
    
    line2 = ax1.plot(x, pnl_df['Net Profit'],
                     color=colors['profit'],
                     linewidth=3,
                     marker='o',
                     markersize=10,
                     markerfacecolor=colors['profit'],
                     markeredgecolor='white',
                     markeredgewidth=2,
                     label='Net Profit',
                     zorder=3)
    
    # Add colored markers for profit/loss
    for i, (xi, yi, c) in enumerate(zip(x, pnl_df['Net Profit'], profit_colors)):
        ax1.plot(xi, yi, 'o', markersize=10, 
                color=c, markeredgecolor='white', markeredgewidth=2, zorder=4)
    
    # Plot Margin (%) on secondary axis
    if 'Margin (%)' in pnl_df.columns:
        line3 = ax2.plot(x, pnl_df['Margin (%)'],
                        color=colors['margin'],
                        linewidth=2,
                        linestyle='--',
                        marker='D',
                        markersize=8,
                        markerfacecolor=colors['margin'],
                        markeredgecolor='white',
                        markeredgewidth=2,
                        label='Margin (%)',
                        zorder=3)
    
    # Add value annotations
    for i, (xi, period) in enumerate(zip(x, pnl_df['Period'])):
        # Revenue annotation
        revenue_val = pnl_df['Revenue'].iloc[i]
        ax1.annotate(f'IDR {revenue_val:,.0f}',
                    xy=(xi, revenue_val),
                    xytext=(0, 15),
                    textcoords='offset points',
                    ha='center',
                    fontsize=9,
                    color=colors['revenue'],
                    weight='bold',
                    bbox=dict(boxstyle='round,pad=0.5', 
                            facecolor='white', 
                            edgecolor=colors['revenue'],
                            alpha=0.9))
        
        # Net Profit annotation
        profit_val = pnl_df['Net Profit'].iloc[i]
        profit_color = colors['profit'] if profit_val >= 0 else colors['loss']
        ax1.annotate(f'IDR {profit_val:,.0f}',
                    xy=(xi, profit_val),
                    xytext=(0, -25),
                    textcoords='offset points',
                    ha='center',
                    fontsize=9,
                    color=profit_color,
                    weight='bold',
                    bbox=dict(boxstyle='round,pad=0.5',
                            facecolor='white',
                            edgecolor=profit_color,
                            alpha=0.9))
        
        # Margin annotation
        if 'Margin (%)' in pnl_df.columns:
            margin_val = pnl_df['Margin (%)'].iloc[i]
            ax2.annotate(f'{margin_val:.1f}%',
                        xy=(xi, margin_val),
                        xytext=(20, 8),
                        textcoords='offset points',
                        ha='left',
                        fontsize=9,
                        color=colors['margin'],
                        weight='bold',
                        bbox=dict(boxstyle='round,pad=0.5',
                                facecolor='white',
                                edgecolor=colors['margin'],
                                alpha=0.9))
    
    # Formatting
    ax1.set_xlabel('Period', fontsize=14, weight='bold')
    ax1.set_ylabel('Amount (IDR)', fontsize=14, weight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(x_labels, fontsize=12)
    ax1.tick_params(axis='y', labelsize=12)
    ax1.grid(True, alpha=0.3, linestyle='-', linewidth=0.5)
    ax1.set_axisbelow(True)
    
    if 'Margin (%)' in pnl_df.columns:
        ax2.set_ylabel('Margin (%)', fontsize=14, weight='bold', color=colors['margin'])
        ax2.tick_params(axis='y', labelcolor=colors['margin'], labelsize=12)
        ax2.set_ylim(bottom=0)
    
    # Title
    if title:
        fig.suptitle(title, fontsize=18, weight='bold', color='#2c3e50')
    
    # Legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    if 'Margin (%)' in pnl_df.columns:
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, 
                  loc='upper center', bbox_to_anchor=(0.5, -0.1),
                  ncol=3, fontsize=12, frameon=True, fancybox=True)
    else:
        ax1.legend(loc='upper center', bbox_to_anchor=(0.5, -0.1),
                  ncol=2, fontsize=12, frameon=True, fancybox=True)
    
    # Layout
    plt.tight_layout()
    
    # Save
    if not filename.endswith(".png"):
        filename = filename + ".png"
    
    plt.savefig(filename, dpi=dpi, bbox_inches='tight', facecolor='white')
    plt.close()
    
    print(f"✅ Chart successfully saved as PNG: {filename}")
    print(f"   Resolution: {int(14*dpi)} x {int(7*dpi)} pixels (~{dpi} DPI)")


def generate_insights(pnl_df):
    # Pastikan ada kolom Margin
    pnl_df = pnl_df.copy()
    pnl_df['Margin (%)'] = (pnl_df['Net Profit'] / pnl_df['Revenue']) * 100

    insights = []
    insights.append("=== KEY INSIGHTS (Auto-Generated) ===\n")

    # 1 - Revenue & Expense trend
    pnl_sorted = pnl_df.sort_values(['Year', 'Month'])
    rev_change = ((pnl_sorted['Revenue'].iloc[-1] - pnl_sorted['Revenue'].iloc[0]) / pnl_sorted['Revenue'].iloc[0]) * 100
    exp_change = ((pnl_sorted['Expense'].iloc[-1] - pnl_sorted['Expense'].iloc[0]) / pnl_sorted['Expense'].iloc[0]) * 100

    if rev_change > 0:
        trend_text = f"Revenue increased by {rev_change:.1f}%"
    elif rev_change < 0:
        trend_text = f"Revenue decreased by {abs(rev_change):.1f}%"
    else:
        trend_text = "Revenue remained stable"

    if exp_change > 0:
        exp_text = f"Expense increased by {exp_change:.1f}%"
    elif exp_change < 0:
        exp_text = f"Expense decreased by {abs(exp_change):.1f}%"
    else:
        exp_text = "Expense remained stable"

    insights.append(f"1. {trend_text} from {pnl_sorted['Period'].iloc[0]} to {pnl_sorted['Period'].iloc[-1]}, while {exp_text}.")

    # 2 - Margin performance
    best_margin = pnl_df.loc[pnl_df['Margin (%)'].idxmax()]
    worst_margin = pnl_df.loc[pnl_df['Margin (%)'].idxmin()]
    insights.append(f"2. Best margin was in {best_margin['Period']} ({best_margin['Margin (%)']:.1f}%), "
                    f"while the lowest was in {worst_margin['Period']} ({worst_margin['Margin (%)']:.1f}%).")

    # 3 - Expense efficiency
    avg_expense_ratio = (pnl_df['Expense'] / pnl_df['Revenue']).mean() * 100
    insights.append(f"3. On average, expenses account for {avg_expense_ratio:.1f}% of revenue — "
                    f"{'good cost control' if avg_expense_ratio < 70 else 'consider cost optimization'}.")

    # 4 - Net Profit direction
    if pnl_sorted['Net Profit'].iloc[-1] > pnl_sorted['Net Profit'].iloc[0]:
        profit_trend = "Net profit is improving over time."
    else:
        profit_trend = "Net profit shows a declining trend."

    insights.append(f"4. {profit_trend}")

    # 5 - Most Efficient month
    best_efficiency = pnl_df.loc[(pnl_df['Expense']/pnl_df['Revenue']).idxmin()]
    insights.append(f"5. Most cost-efficient month was {best_efficiency['Period']} "
                    f"with only {(best_efficiency['Expense']/best_efficiency['Revenue']*100):.1f}% expense-to-revenue ratio.")

    return "\n".join(insights)

# --- MAIN EXECUTION ---
def main():
    print("🚀 Starting Finance Automation...")
    transactions = load_and_clean_data()
    pnl = generate_pnl(transactions)
    plot_and_save(pnl)
    insights = generate_insights(pnl)

    # Import raw data for saving
    sales = pd.read_excel(f"datasets/{INPUT_FILES['sales']}")
    expenses = pd.read_excel(f"datasets/{INPUT_FILES['expenses']}")
    coa = pd.read_excel(f"datasets/{INPUT_FILES['coa']}")

    # Save to Excel
    with pd.ExcelWriter(OUTPUT_FILE, engine='openpyxl') as writer:
        transactions.to_excel(writer, sheet_name='Transactions', index=False)
        pnl.to_excel(writer, sheet_name='Monthly_PnL', index=False)
        sales.to_excel(writer, sheet_name='Sales', index=False)
        expenses.to_excel(writer, sheet_name='Expenses', index=False)
        coa.to_excel(writer, sheet_name='Mapping_COA', index=False)

    # Save insights
    with open('output/insights_summary.txt', 'w') as f:
        f.write(insights)

    print(f"✅ Report saved to: {OUTPUT_FILE}")
    print(f"📊 Chart saved to: {CHART_FILE}")
    print(f"💡 Insights saved to: insights_summary.txt")
    print("\n" + insights)

if __name__ == "__main__":
    main()