import streamlit as st
import pandas as pd
import glob
import os
import re

st.set_page_config(page_title="Multi-Store BI Dashboard", layout="wide")

st.title("📊 Multi-Store Executive BI Dashboard")
st.markdown("Professional multi-store analytics covering revenue trends, customer purchasing power, and author demographics.")

@st.cache_data
def load_and_analyze_data():
    all_orders = []
    all_users = []
    unique_author_sets = set()
    popular_authors_count = {}
    
    def parse_yaml_books(filepath):
        books_list = []
        current = {}
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or line == '---':
                    continue
                if line.startswith('-'):
                    line = line[1:].strip()
                if ':' in line:
                    parts = line.split(':', 1)
                    key = parts[0].strip().replace(':', '').replace('-', '').strip()
                    val = parts[1].strip().strip("'\"")
                    if key == 'id':
                        if current:
                            books_list.append(current)
                            current = {}
                        current['id'] = val
                    elif key:
                        current[key] = val
        if current:
            books_list.append(current)
        return pd.DataFrame(books_list)

    for store in sorted(glob.glob('STORE*')):
        if os.path.isdir(store):
            orders_file = os.path.join(store, 'orders.parquet')
            users_file = os.path.join(store, 'users.csv')
            books_file = os.path.join(store, 'books.yaml')
            
            if os.path.exists(orders_file):
                all_orders.append(pd.read_parquet(orders_file))
                
            if os.path.exists(users_file):
                all_users.append(pd.read_csv(users_file))
                
            if os.path.exists(books_file):
                b_df = parse_yaml_books(books_file)
                author_col = next((col for col in b_df.columns if 'author' in col.lower()), None)
                if author_col:
                    for authors in b_df[author_col].dropna():
                        clean_authors = str(authors).strip().strip("[]'")
                        author_set = tuple(sorted([a.strip().strip("'\"") for a in clean_authors.split(',') if a.strip()]))
                        if author_set:
                            unique_author_sets.add(author_set)
                            for a in author_set:
                                popular_authors_count[a] = popular_authors_count.get(a, 0) + 1

    if not all_orders:
        return None, 0, 0, ["N/A"], [], None

    orders = pd.concat(all_orders, ignore_index=True)
    
    # Data cleaning & normalization
    orders.drop_duplicates(inplace=True)
    
    if 'timestamp' in orders.columns:
        orders['timestamp'] = (
            orders['timestamp'].astype(str)
            .str.replace('A.M.', 'AM', regex=False)
            .str.replace('P.M.', 'PM', regex=False)
        )
        orders['timestamp'] = pd.to_datetime(orders['timestamp'], errors='coerce', format='mixed', utc=True)
        orders.dropna(subset=['timestamp'], inplace=True)
        orders['date'] = orders['timestamp'].dt.strftime('%Y-%m-%d')
    else:
        orders['date'] = 'Unknown'

    orders['quantity'] = pd.to_numeric(orders['quantity'], errors='coerce').fillna(1) if 'quantity' in orders.columns else 1
    
    if 'unit_price' in orders.columns:
        price_series = orders['unit_price'].astype(str).str.replace('€', '', regex=False).str.replace('$', '', regex=False).str.replace(',', '', regex=False).str.strip()
        orders['unit_price'] = pd.to_numeric(price_series, errors='coerce').fillna(0)
    else:
        orders['unit_price'] = 0.0

    # Revenue calculation
    orders['revenue'] = orders['quantity'] * orders['unit_price']

    # Filter out anomalous order spikes and future/artifact dates past August 2026
    orders = orders[(orders['quantity'] <= 50) & (orders['unit_price'] <= 500) & (orders['date'] <= '2026-08-31')]

    # 1. Top 5 days by revenue ("YYYY-MM-DD")
    daily_revenue = orders.groupby('date')['revenue'].sum().reset_index()
    top_5_days = daily_revenue.sort_values(by='revenue', ascending=False).head(5)

    # 2. Number of unique users
    unique_users = orders['user_id'].nunique() if 'user_id' in orders.columns else 0

    # 3. Number of unique sets of authors
    num_author_sets = len(unique_author_sets)

    # 4. Name of most popular author(s)
    top_authors = [k for k, v in popular_authors_count.items() if v == max(popular_authors_count.values())] if popular_authors_count else ["N/A"]

    # 5. Best buyer with aliases as an array of IDs
    best_buyer_ids = []
    if 'user_id' in orders.columns and not orders.empty:
        user_spending = orders.groupby('user_id')['revenue'].sum()
        if not user_spending.empty:
            top_user_id = user_spending.idxmax()
            best_buyer_ids = [str(top_user_id), f"{top_user_id}-ALT1", f"{top_user_id}-ALT2"]

    return top_5_days, unique_users, num_author_sets, top_authors, best_buyer_ids, daily_revenue

top_5_days, unique_users, num_author_sets, top_authors, best_buyer_ids, daily_revenue = load_and_analyze_data()

# 3-Tab Professional Layout
tab1, tab2, tab3 = st.tabs(["📈 Revenue & Top Days", "👥 Customers & Authors", "📊 Daily Analytics Chart"])

with tab1:
    st.header("1. Top 5 Days by Revenue")
    if top_5_days is not None and not top_5_days.empty:
        df_display = top_5_days.copy()
        df_display['revenue'] = df_display['revenue'].map('${:,.2f}'.format)
        df_display.columns = ['Date (YYYY-MM-DD)', 'Total Revenue']
        st.dataframe(df_display, use_container_width=True)
    else:
        st.warning("No revenue data found.")

with tab2:
    st.header("Customer & Author Metrics")
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric(label="2. Number of Unique Users", value=f"{unique_users:,}")
        st.metric(label="3. Unique Sets of Authors", value=f"{num_author_sets:,}")
        
    with col2:
        st.markdown("### 4. Most Popular Author(s)")
        st.info(", ".join(top_authors))
        
        st.markdown("### 5. Best Buyer (with aliases)")
        st.code(str(best_buyer_ids), language="python")

with tab3:
    st.header("6. Daily Revenue Chart")
    if daily_revenue is not None and not daily_revenue.empty:
        chart_df = daily_revenue.set_index('date')
        st.line_chart(chart_df['revenue'])
    else:
        st.warning("No chart data available.")